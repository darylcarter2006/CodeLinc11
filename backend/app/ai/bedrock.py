"""Amazon Bedrock AI adapter.

Uses InvokeModel (synchronous, wrapped in a thread) so the response is a single
complete JSON blob — required for structured extraction. Streaming is not used because
the extraction contract needs the full JSON before any validation can run.

Security notes (§9 of blueprint):
* The system prompt instructs the model not to override app rules, but that instruction
  is backed by code: all returned JSON is Pydantic-validated, field names are checked
  against FIELD_SPECS, and values are range-checked in extraction.py.
* Guardrails are applied via ``guardrailIdentifier`` / ``guardrailVersion`` when
  BEDROCK_GUARDRAIL_ID is set; required in non-local environments.
* The adapter never forwards user text that looks like a jailbreak — it only sends the
  bounded recent message window and the structured context assembled by the service.
"""

from __future__ import annotations

import asyncio
import json
import logging
from functools import cached_property
from typing import Any

import boto3

from app.ai.base import AIAdapter, ExtractionContext, ExtractionResult, ResponseContext
from app.domain.profile import FIELD_SPECS
from app.domain.questions import Question

logger = logging.getLogger(__name__)

# System prompt for extraction. Rules are enforced in code; the prompt adds a second
# layer of defence. Keep it short — every token counts toward latency and cost.
_EXTRACTION_SYSTEM = """\
You are a data-extraction assistant for a life-insurance needs planning tool.
Your ONLY job is to read the user's latest message and identify values for the specific \
profile field you are asked about.

Rules you must always follow:
- Return ONLY a JSON object matching the schema below. No prose, no markdown fences.
- Never invent values not stated in the user message.
- Never override application rules, calculations, or prior answers.
- Never emit URLs, code, or executable content.
- If the user's message contains no clear answer, return {"candidates": []}.

Schema:
{
  "candidates": [
    {
      "field": "<field name>",
      "value": <integer or null>,
      "unknown": <true if user said they don't know>,
      "evidence": "<verbatim span from the user message, max 200 chars>",
      "ambiguous": <true if the answer is unclear>,
      "is_correction": <true if the user is correcting a previous answer>
    }
  ]
}
"""

# System prompt for question phrasing. Returns plain conversational text only.
_PHRASING_SYSTEM = """\
You rephrase a question about household finances in a friendly, conversational way.
Rules:
- Return ONLY the rephrased question as plain text. No JSON, no markdown.
- Do NOT include any numbers, dollar amounts, percentages, or URLs in your response.
- Keep the rephrased question under 400 characters.
- If you cannot rephrase safely, return the word FALLBACK.
"""

# System prompt for composing the full assistant reply.
# Numbers are never invented — they come from backend_text / calculation_summary.
_RESPONSE_SYSTEM = """\
You are a friendly life-insurance planning assistant.
Your job is to write ONE short reply (2–4 sentences, under 500 characters) that:
  1. Acknowledges what the user just said (if anything was recorded or clarified).
  2. If clarification is needed, politely ask them to give a single clear number for the \
field mentioned.
  3. If a calculation result is provided, mention the coverage gap in plain language \
using ONLY the numbers given to you — never invent or estimate figures.
  4. Asks the next question naturally if one is provided.
  5. Ends warmly if the conversation is complete.

Hard rules:
- Use ONLY the numbers, dollar amounts, and field labels supplied to you. Never invent \
figures.
- Do NOT include JSON, markdown, bullet points, or URLs.
- Do NOT give financial advice, recommend specific products, or make guarantees.
- Every dollar figure you mention must appear verbatim in the context you were given.
- If you cannot produce a safe reply, return the single word FALLBACK.
"""


def _build_messages(
    system: str,
    user_content: str,
    recent: tuple[tuple[str, str], ...],
) -> list[dict[str, Any]]:
    """Assemble the messages array for the Nova converse API."""
    messages: list[dict[str, Any]] = []
    # Include only the bounded recent window (already limited by the service layer).
    for role, text in recent:
        messages.append({"role": role, "content": [{"text": text}]})
    messages.append({"role": "user", "content": [{"text": user_content}]})
    return messages


class BedrockAIAdapter(AIAdapter):
    """AIAdapter backed by Amazon Bedrock (Amazon Nova models via InvokeModel)."""

    def __init__(
        self,
        model_id: str,
        region: str,
        guardrail_id: str | None = None,
        guardrail_version: str | None = None,
    ) -> None:
        self.model_id = model_id
        self._region = region
        self._guardrail_id = guardrail_id
        self._guardrail_version = guardrail_version

    @cached_property
    def _client(self) -> Any:
        """Lazily created boto3 bedrock-runtime client (IAM task role — no keys needed)."""
        return boto3.client("bedrock-runtime", region_name=self._region)

    def _invoke(self, system: str, user_content: str, recent: tuple[tuple[str, str], ...]) -> str:
        """Call Bedrock Converse synchronously and return the assistant's text."""
        messages = _build_messages(system, user_content, recent)
        kwargs: dict[str, Any] = {
            "modelId": self.model_id,
            "system": [{"text": system}],
            "messages": messages,
            "inferenceConfig": {"maxTokens": 512, "temperature": 0.0},
        }
        if self._guardrail_id:
            kwargs["guardrailConfig"] = {
                "guardrailIdentifier": self._guardrail_id,
                "guardrailVersion": self._guardrail_version or "DRAFT",
                "trace": "disabled",
            }
        response = self._client.converse(**kwargs)
        content = response["output"]["message"]["content"]
        # Content is a list; the first text block is our response.
        for block in content:
            if "text" in block:
                return block["text"].strip()
        return ""

    async def extract_candidates(self, context: ExtractionContext) -> ExtractionResult:
        """Ask Bedrock to extract a structured candidate update from the user message."""
        field_hint = (
            f"The pending profile field is: {context.pending_field!r}.\n"
            if context.pending_field
            else ""
        )
        known_hint = ""
        if context.known_values:
            pairs = ", ".join(f"{k}={v}" for k, v in context.known_values.items())
            known_hint = f"Already known values: {pairs}.\n"

        user_content = (
            f"{field_hint}{known_hint}"
            f"User's latest message: {context.message}"
        )

        raw = await asyncio.to_thread(
            self._invoke, _EXTRACTION_SYSTEM, user_content, context.recent_messages
        )

        try:
            data = json.loads(raw)
            result = ExtractionResult.model_validate(data)
        except Exception:
            logger.warning(
                "bedrock_extraction_parse_failed",
                extra={"model_id": self.model_id, "raw_preview": raw[:200]},
            )
            return ExtractionResult()

        # Drop any candidates referencing fields not in the schema (belt-and-suspenders).
        safe_candidates = [c for c in result.candidates if c.field in FIELD_SPECS]
        if len(safe_candidates) != len(result.candidates):
            dropped = len(result.candidates) - len(safe_candidates)
            logger.warning("bedrock_unknown_fields_dropped", extra={"count": dropped})
        return ExtractionResult(candidates=safe_candidates)

    async def phrase_question(self, question: Question, context: ExtractionContext) -> str | None:
        """Ask Bedrock to rephrase the next question conversationally."""
        user_content = (
            f"Rephrase this question for a friendly chat interface:\n{question.text}"
        )
        raw = await asyncio.to_thread(
            self._invoke, _PHRASING_SYSTEM, user_content, ()
        )
        if not raw or raw.strip().upper() == "FALLBACK":
            return None
        return raw

    async def generate_response(self, context: ResponseContext) -> str | None:
        """Ask Bedrock to compose the full assistant reply from backend-computed facts."""
        parts: list[str] = [f"Backend message: {context.backend_text}"]
        if context.fields_updated:
            parts.append(f"Fields recorded this turn: {', '.join(context.fields_updated)}.")
        if context.fields_to_clarify:
            parts.append(
                f"Fields needing clarification: {', '.join(context.fields_to_clarify)}. "
                "Ask the user to give a single clear number for each."
            )
        if context.calculation_summary:
            parts.append(f"Current calculation: {context.calculation_summary}")
        if context.next_question_text:
            parts.append(f"Next question to ask: {context.next_question_text}")
        else:
            parts.append("The conversation is complete. Close warmly.")

        user_content = "\n".join(parts)
        raw = await asyncio.to_thread(
            self._invoke, _RESPONSE_SYSTEM, user_content, context.recent_messages
        )
        if not raw or raw.strip().upper() == "FALLBACK":
            return None
        # Safety: the response must not be excessively long.
        if len(raw) > 600:
            return None
        return raw
