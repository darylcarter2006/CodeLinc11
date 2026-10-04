"""Coverage Compass AI: onboarding extraction and grounded chat.

Prompts come from ``docs/coverage-compass/HANDOFF.md``. The model never calculates:
extraction output is filtered through ``clean()``, and chat is grounded in a calculation
the server computes from the profile (the browser's figures are ignored).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from app.ai.base import (
    AIAdapter,
    ChatMessage,
    ModelFailed,
    ModelThrottled,
    ModelUnavailable,
)
from app.contracts.ai import ChatRequest, ExtractRequest, ExtractResponse
from app.domain.compass import CompassProfile, clean, compute
from app.errors import AIFailed, AIUnavailable, RateLimited, ValidationFailed

logger = logging.getLogger(__name__)

# Ceilings, not targets: thinking counts toward max_tokens, so leave room beyond the short
# replies the prompts ask for (an 8-word ack, a <120-word answer).
EXTRACT_MAX_TOKENS = 4000
CHAT_MAX_TOKENS = 8000
CHAT_HISTORY_TURNS = 8
ACK_MAX_WORDS = 8
ACK_MAX_CHARS = 120
ANSWER_MAX_CHARS = 400

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
_LINK_RE = re.compile(r"https?://|www\.", re.IGNORECASE)

EXTRACT_SYSTEM = "You fill in a form from a chat message. Reply with only a JSON object."

EXTRACT_PROMPT = """You help fill in a life insurance needs profile from a casual chat.
Extract every field the person states or corrects in their latest message. Fields: deps (array of "partner","kids","relative", or ["none"]), children (count), youngest (age in years), age, income (yearly USD), years (years of income support), mortgage (USD balance left), mortgageYears, otherDebt (USD total), college ("public","half","none"), group (USD life insurance through work; a multiple of salary means multiply by income {income}), policies (USD of policies they own), savings (USD to count). "None" or "no" for a dollar field means 0.
We just asked about "{asked_field}": "{question}"
Current profile: {profile}
Latest message: \"\"\"{message}\"\"\"
Reply with only JSON: {{"updates": {{only fields clearly stated}}, "ack": "a warm acknowledgement of at most 8 words", "answer": "if they asked a question, a calm plain answer under 45 words; otherwise an empty string"}}"""  # noqa: E501

CHAT_SYSTEM = """You are the assistant inside Coverage Compass, an educational life insurance needs tool.
Tone: calm, warm, plain language. Define jargon in a few words. Never alarming; avoid words like "shortfall" or "at risk".
Keep answers under 120 words in short paragraphs. No headings or tables. Use the person's own coverage and numbers below and show simple math.
Do not recommend companies or specific products, and do not quote prices. If asked about something unrelated to life insurance planning, gently steer back.
If they mention a life change or a correction, explain the likely effect and tell them they can update it in the My info tab.
Method: income need = 75% of income × years of support; debts = mortgage + other debts; college = $100,000 per child (public) or $50,000 (half); final expenses $15,000; minus coverage in place; rounded up to the nearest $25,000.
Coverage in place: work group life {group} (usually ends when leaving the job), policies they own {policies}, savings counted {savings}; total {existing}.
Profile: {profile}
Calculation: {calculation}
{who}"""  # noqa: E501

EXAMPLE_WHO = (
    "These are example numbers for a sample person named Maya, not the user's own. "
    "If they ask about their own situation, suggest they create an account."
)


def _usd(amount: float) -> str:
    return f"${round(amount):,}"


def _quote_safe(text: str) -> str:
    # The message sits inside triple quotes in the prompt; keep it from closing them.
    return text.replace('"""', "'''")


def _one_line(text: str, limit: int) -> str:
    return " ".join(text.split())[:limit]


def build_extract_prompt(req: ExtractRequest) -> str:
    profile = req.profile
    return EXTRACT_PROMPT.format(
        income=_usd(profile.income) if profile.income > 0 else '"unknown"',
        asked_field=req.askedField,
        question=_quote_safe(_one_line(req.question, 500)),
        profile=json.dumps(profile.model_dump(), separators=(",", ":")),
        message=_quote_safe(req.message),
    )


def build_chat_system(profile: CompassProfile, first_name: str | None, example: bool) -> str:
    calc = compute(profile)
    calculation = {
        "lines": [[line.label, round(line.amount)] for line in calc.lines],
        "total": round(calc.total),
        "gap": round(calc.gap),
        "suggested": calc.suggested,
        "termYears": calc.term,
    }
    if example:
        who = EXAMPLE_WHO
    else:
        name = _one_line(first_name or "", 40)
        who = f"The person's first name is {name}." if name else ""
    return CHAT_SYSTEM.format(
        group=_usd(profile.group),
        policies=_usd(profile.policies),
        savings=_usd(profile.savings),
        existing=_usd(calc.existing),
        profile=json.dumps(profile.model_dump(), separators=(",", ":")),
        calculation=json.dumps(calculation, separators=(",", ":")),
        who=who,
    ).rstrip()


def parse_extraction(raw: str) -> ExtractResponse:
    """Turn model text into a safe response. Anything unusable becomes empty fields, so
    the front end falls back to its local parser for the question it asked."""
    match = _JSON_OBJECT_RE.search(raw)
    data: Any = None
    if match:
        try:
            data = json.loads(match.group(0))
        except ValueError:
            data = None
    if not isinstance(data, dict):
        return ExtractResponse(updates={}, ack="", answer="")
    return ExtractResponse(
        updates=clean(data.get("updates")),
        ack=_clean_text(data.get("ack"), ACK_MAX_CHARS, max_words=ACK_MAX_WORDS),
        answer=_clean_text(data.get("answer"), ANSWER_MAX_CHARS),
    )


def _clean_text(value: object, limit: int, max_words: int | None = None) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    if _LINK_RE.search(text):
        return ""  # links from the model are never shown as authoritative
    if max_words is not None:
        text = " ".join(text.split(" ")[:max_words])
    return text[:limit]


def chat_history(req: ChatRequest) -> list[ChatMessage]:
    """Last turns, starting with the user and alternating roles, as providers require."""
    turns = [ChatMessage(t.role, t.content.strip()) for t in req.messages if t.content.strip()]
    turns = turns[-CHAT_HISTORY_TURNS:]
    while turns and turns[0].role != "user":
        turns.pop(0)
    merged: list[ChatMessage] = []
    for turn in turns:
        if merged and merged[-1].role == turn.role:
            merged[-1] = ChatMessage(turn.role, f"{merged[-1].content}\n\n{turn.content}")
        else:
            merged.append(turn)
    if not merged or merged[-1].role != "user":
        raise ValidationFailed("The conversation must end with a user message.")
    return merged


def _translate(exc: Exception) -> Exception:
    if isinstance(exc, ModelUnavailable):
        return AIUnavailable()
    if isinstance(exc, ModelThrottled):
        return RateLimited()
    return AIFailed()


class CompassAIService:
    def __init__(self, ai: AIAdapter, timeout_seconds: float) -> None:
        self._ai = ai
        self._timeout = timeout_seconds

    async def extract(self, req: ExtractRequest) -> ExtractResponse:
        started = time.perf_counter()
        try:
            raw = await asyncio.wait_for(
                self._ai.generate(
                    EXTRACT_SYSTEM,
                    [ChatMessage("user", build_extract_prompt(req))],
                    tier="fast",
                    max_tokens=EXTRACT_MAX_TOKENS,
                ),
                self._timeout,
            )
        except ModelUnavailable:
            raise AIUnavailable() from None
        except ModelThrottled:
            raise RateLimited() from None
        except (ModelFailed, TimeoutError):
            # The front end falls back to its local parser on an empty result.
            self._log("ai_extract_failed", started)
            return ExtractResponse(updates={}, ack="", answer="")
        self._log("ai_extract", started)
        return parse_extraction(raw)

    async def chat(self, req: ChatRequest) -> AsyncIterator[str]:
        """Start the stream. Errors before the first chunk become HTTP errors; after it,
        the stream just ends (the status line has already been sent)."""
        history = chat_history(req)
        context = req.context
        system = build_chat_system(context.profile, context.firstName, context.example)
        started = time.perf_counter()
        try:
            stream = self._ai.stream(system, history, tier="smart", max_tokens=CHAT_MAX_TOKENS)
            iterator = aiter(stream)
            first = await asyncio.wait_for(anext(iterator), self._timeout)
        except StopAsyncIteration:
            raise AIFailed() from None
        except (ModelUnavailable, ModelThrottled, ModelFailed) as exc:
            raise _translate(exc) from None
        except TimeoutError:
            raise AIFailed() from None
        self._log("ai_chat_started", started)
        return self._rest(first, iterator, started)

    async def _rest(
        self, first: str, iterator: AsyncIterator[str], started: float
    ) -> AsyncIterator[str]:
        yield first
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(anext(iterator), self._timeout)
                except StopAsyncIteration:
                    break
                yield chunk
        except Exception:
            logger.warning("ai_chat_interrupted", extra={"ai_model_id": self._ai.model_id})
        finally:
            self._log("ai_chat_finished", started)

    def _log(self, event: str, started: float) -> None:
        logger.info(
            event,
            extra={
                "ai_model_id": self._ai.model_id,
                "ai_latency_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
