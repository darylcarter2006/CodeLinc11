"""OpenAI adapter — wraps the official ``openai`` SDK to satisfy ``AIAdapter``.

Configure via environment variables (or .env):
    AI_PROVIDER=openai
    OPENAI_API_KEY=sk-...
    OPENAI_MODEL_FAST=gpt-4o-mini       # optional override, used for "fast" tier
    OPENAI_MODEL_SMART=gpt-4o           # optional override, used for "smart" tier
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import openai

from app.ai.base import (
    AIAdapter,
    CandidateUpdate,
    ChatMessage,
    ExtractionContext,
    ExtractionResult,
    ModelFailed,
    ModelThrottled,
    ModelTier,
    ModelUnavailable,
)
from app.domain.questions import Question

logger = logging.getLogger(__name__)

# Default model names — callers may override via constructor.
_DEFAULT_FAST = "gpt-4o-mini"
_DEFAULT_SMART = "gpt-4o"

_EXTRACT_SYSTEM = (
    "You extract profile field values from a user's message. "
    "Reply ONLY with valid JSON matching the schema: "
    '{"candidates": [{"field": "<name>", "value": <int|null>, "evidence": "<span>", '
    '"unknown": false, "ambiguous": false, "is_correction": false}]}'
)


def _to_sdk_messages(
    system: str, messages: list[ChatMessage]
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = [{"role": "system", "content": system}]
    for m in messages:
        result.append({"role": m.role, "content": m.content})
    return result


def _map_error(exc: Exception) -> Exception:
    """Translate openai SDK errors to AIAdapter error types."""
    if isinstance(exc, openai.AuthenticationError):
        logger.error("openai_auth_error: check OPENAI_API_KEY")
        return ModelUnavailable()
    if isinstance(exc, openai.RateLimitError):
        return ModelThrottled()
    if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError)):
        return ModelUnavailable()
    if isinstance(exc, openai.APIStatusError):
        return ModelFailed()
    return ModelFailed()


class OpenAIAdapter(AIAdapter):
    """Calls the OpenAI Chat Completions and Responses APIs."""

    model_id = "openai"

    def __init__(
        self,
        api_key: str,
        model_fast: str = _DEFAULT_FAST,
        model_smart: str = _DEFAULT_SMART,
    ) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._models: dict[ModelTier, str] = {
            "fast": model_fast,
            "smart": model_smart,
        }

    def _model(self, tier: ModelTier) -> str:
        return self._models[tier]

    # ------------------------------------------------------------------
    # Session question-flow helpers (used by ConversationService)
    # ------------------------------------------------------------------

    async def extract_candidates(self, context: ExtractionContext) -> ExtractionResult:
        """Ask the model to identify profile-field values in the user's latest message."""
        prompt_lines = [f'User message: "{context.message}"']
        if context.pending_field:
            prompt_lines.append(f"We are currently asking about: {context.pending_field}")
        if context.known_values:
            prompt_lines.append(f"Known values so far: {context.known_values}")

        user_content = "\n".join(prompt_lines)
        try:
            response = await self._client.chat.completions.create(
                model=self._model("fast"),
                messages=[
                    {"role": "system", "content": _EXTRACT_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=300,
                temperature=0,
            )
        except Exception as exc:
            raise _map_error(exc) from exc

        raw = (response.choices[0].message.content or "").strip()
        return _parse_candidates(raw)

    async def phrase_question(
        self, question: Question, context: ExtractionContext
    ) -> str | None:
        """Return a friendlier phrasing of *question*, or None to use approved copy."""
        system = (
            "You rephrase a life-insurance onboarding question in a warm, plain-language way. "
            "Keep it one sentence, no jargon. Return only the rephrased question text."
        )
        known = context.known_values
        user_content = (
            f"Rephrase this question for a user: {question.text!r}\n"
            f"Known profile values: {known}"
        )
        try:
            response = await self._client.chat.completions.create(
                model=self._model("fast"),
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=80,
                temperature=0.3,
            )
        except Exception as exc:
            logger.warning("openai_phrase_question_error: %s", exc)
            return None  # fall back to approved copy silently

        text = (response.choices[0].message.content or "").strip()
        return text or None

    # ------------------------------------------------------------------
    # Plain-text generate / stream (used by CompassAIService)
    # ------------------------------------------------------------------

    async def generate(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        tier: ModelTier,
        max_tokens: int,
    ) -> str:
        sdk_messages = _to_sdk_messages(system, messages)
        try:
            response = await self._client.chat.completions.create(
                model=self._model(tier),
                messages=sdk_messages,
                max_tokens=max_tokens,
                temperature=0.4,
            )
        except Exception as exc:
            raise _map_error(exc) from exc

        return (response.choices[0].message.content or "").strip()

    def stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        tier: ModelTier,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        """Return an async iterator that yields text chunks as they arrive."""
        return _OpenAIStream(
            self._client,
            self._model(tier),
            _to_sdk_messages(system, messages),
            max_tokens,
        )


class _OpenAIStream:
    """Wraps openai's async streaming response as an AsyncIterator[str]."""

    def __init__(
        self,
        client: openai.AsyncOpenAI,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> None:
        self._client = client
        self._model = model
        self._messages = messages
        self._max_tokens = max_tokens
        self._stream: openai.AsyncStream | None = None

    def __aiter__(self) -> _OpenAIStream:
        return self

    async def __anext__(self) -> str:
        if self._stream is None:
            try:
                self._stream = await self._client.chat.completions.create(
                    model=self._model,
                    messages=self._messages,
                    max_tokens=self._max_tokens,
                    temperature=0.4,
                    stream=True,
                )
            except Exception as exc:
                raise _map_error(exc) from exc

        try:
            async for chunk in self._stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    return delta
            raise StopAsyncIteration
        except StopAsyncIteration:
            raise
        except Exception as exc:
            raise _map_error(exc) from exc


# ------------------------------------------------------------------
# Candidate extraction helper
# ------------------------------------------------------------------

import json  # noqa: E402 — placed here so the module-level imports stay clean
import re

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_candidates(raw: str) -> ExtractionResult:
    match = _JSON_RE.search(raw)
    if not match:
        return ExtractionResult()
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return ExtractionResult()
    if not isinstance(data, dict):
        return ExtractionResult()

    candidates: list[CandidateUpdate] = []
    for item in data.get("candidates", []):
        if not isinstance(item, dict):
            continue
        field = item.get("field", "")
        evidence = str(item.get("evidence") or field or "stated")
        try:
            candidates.append(
                CandidateUpdate(
                    field=field,
                    value=item.get("value"),
                    unknown=bool(item.get("unknown", False)),
                    ambiguous=bool(item.get("ambiguous", False)),
                    is_correction=bool(item.get("is_correction", False)),
                    evidence=evidence[:200] or field[:200] or "stated",
                )
            )
        except Exception:
            continue  # skip malformed entries from the model

    return ExtractionResult(candidates=candidates[:10])
