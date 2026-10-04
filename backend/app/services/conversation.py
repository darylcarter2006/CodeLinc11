"""One chat turn: extract candidate facts, merge, recalculate, choose the next question.

The backend owns the question plan and every number. The AI adapter only proposes
values and (optionally) rewords the next question; if it fails, the turn still works.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

from app.ai.base import AIAdapter, ExtractionContext, ExtractionResult, ResponseContext
from app.contracts.requests import MessageRequest
from app.contracts.responses import MessageResponse, MessagesResponse
from app.calculators.registry import get_policy
from app.domain.profile import FIELD_SPECS, Profile, ProfileValue
from app.domain.questions import REVIEW_FIELD, Question, fields_needing_review, next_question
from app.domain.records import ConversationState, MessageRecord, SessionRecord
from app.errors import TurnLimitExceeded, ValidationFailed
from app.repositories.base import SessionRepository, SessionUpdate
from app.security.redaction import log_safe_session_id
from app.security.tokens import new_id
from app.services.extraction import ExtractionOutcome, validate_candidates
from app.services.explanation import explain
from app.services.idempotency import find_replay, new_record, request_hash
from app.services.presenters import to_message_out
from app.services.profiles import build_profile_response, load_for_update
from app.services.sessions import Clock
from app.settings import Settings

logger = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 500

AI_FALLBACK_NOTE = (
    "I couldn't process that automatically. You can answer with a number, "
    "or edit your answers directly."
)
NO_ANSWER_NOTE = "I didn't catch an answer to that."
CONFIRMED_NOTE = "Thanks for confirming."
DONE_MESSAGE = "That's everything I need. Your estimate is ready to review."

_AFFIRMATIVE_RE = re.compile(
    r"^\s*(yes|yep|yeah|correct|confirm(ed)?|looks (good|right)|that'?s (right|correct)|"
    r"all good)\b[\s.!]*$",
    re.IGNORECASE,
)
_UNSAFE_PHRASING_RE = re.compile(r"\d|https?:|www\.", re.IGNORECASE)
_UNSAFE_RESPONSE_RE = re.compile(r"https?:|www\.", re.IGNORECASE)

WARNING_AI_FALLBACK = "ai_fallback_used"
WARNING_CLARIFICATION = "clarification_needed"


def _clarify_text(field: str) -> str:
    label = FIELD_SPECS[field].label.lower()
    return (
        f"I want to be sure I record {label} correctly. "
        "Could you answer with a single number, or say you don't know?"
    )


def _noted_text(updates: dict[str, ProfileValue[Any]]) -> str:
    known = [FIELD_SPECS[n].label.lower() for n, v in updates.items() if v.value is not None]
    unknown = [FIELD_SPECS[n].label.lower() for n, v in updates.items() if v.value is None]
    parts = []
    if known:
        parts.append(f"Thanks, I've noted your {', '.join(known)}.")
    if unknown:
        parts.append(f"No problem, I've marked {', '.join(unknown)} as unknown for now.")
    return " ".join(parts)


def _known_values(profile: Profile) -> dict[str, object]:
    values: dict[str, object] = {}
    for name in FIELD_SPECS:
        field = profile.field(name)
        if field is None:
            continue
        if isinstance(field.value, list):
            values[name] = sum(item.amount for item in field.value)
        else:
            values[name] = field.value
    return values


def _confirm_fields(profile: Profile, fields: list[str]) -> Profile:
    changes: dict[str, Any] = {}
    for name in fields:
        field = profile.field(name)
        if field is not None and not field.confirmed:
            changes[name] = field.model_copy(update={"confirmed": True})
    return profile.with_fields(changes) if changes else profile


class ConversationService:
    def __init__(
        self, repo: SessionRepository, ai: AIAdapter, settings: Settings, clock: Clock
    ) -> None:
        self._repo = repo
        self._ai = ai
        self._settings = settings
        self._clock = clock

    async def history(self, session: SessionRecord) -> MessagesResponse:
        messages = await self._repo.list_messages(
            session.id, self._settings.message_history_turns * 2
        )
        return MessagesResponse(
            session_id=session.id, messages=[to_message_out(m) for m in messages]
        )

    async def handle_turn(self, session: SessionRecord, request: MessageRequest) -> MessageResponse:
        if len(request.text) > self._settings.message_max_chars:
            raise ValidationFailed(
                f"Messages are limited to {self._settings.message_max_chars} characters."
            )
        req_hash = request_hash("message", request.model_dump(mode="json"))

        async with self._repo.session_lock(session.id):
            replay = await find_replay(self._repo, session.id, request.client_request_id, req_hash)
            if replay is not None:
                return MessageResponse.model_validate(replay.response)

            session = await load_for_update(self._repo, session.id, request.expected_revision)
            if session.turn_count >= self._settings.session_turn_limit:
                raise TurnLimitExceeded()

            recent = await self._repo.list_messages(
                session.id, self._settings.message_history_turns * 2
            )
            context = ExtractionContext(
                message=request.text,
                pending_field=session.conversation_state.pending_field,
                known_values=_known_values(session.profile),
                recent_messages=tuple((m.role, m.content) for m in recent),
            )

            warnings: list[str] = []
            started = time.perf_counter()
            result = await self._extract(context)
            ai_latency_ms = round((time.perf_counter() - started) * 1000, 1)
            if result is None:
                warnings.append(WARNING_AI_FALLBACK)
                result = ExtractionResult()
            outcome = validate_candidates(result, request.text, session.profile)
            if outcome.clarify:
                warnings.append(WARNING_CLARIFICATION)

            profile = (
                session.profile.with_fields(outcome.updates) if outcome.updates else session.profile
            )
            confirmed_review = False
            if context.pending_field == REVIEW_FIELD and _AFFIRMATIVE_RE.match(request.text):
                profile = _confirm_fields(profile, fields_needing_review(profile))
                confirmed_review = True

            question = next_question(profile)
            breakdown = get_policy().calculate(profile)
            calculation_summary = explain(breakdown)
            assistant_message = await self._compose(
                context,
                outcome,
                question,
                confirmed_review,
                ai_failed=WARNING_AI_FALLBACK in warnings,
                calculation_summary=calculation_summary,
            )

            new_revision = request.expected_revision + 1
            base = build_profile_response(session.id, new_revision, profile)
            response = MessageResponse(
                **base.model_dump(), assistant_message=assistant_message, warnings=warnings
            )

            now = self._clock()
            turn_id = new_id("turn")
            await self._repo.commit(
                session.id,
                SessionUpdate(
                    expected_revision=request.expected_revision,
                    profile=profile,
                    conversation_state=ConversationState(
                        pending_field=question.field if question else None
                    ),
                    increment_turn=True,
                    messages=(
                        MessageRecord(
                            id=new_id("msg"),
                            session_id=session.id,
                            role="user",
                            content=request.text,
                            turn_id=turn_id,
                            created_at=now,
                        ),
                        MessageRecord(
                            id=new_id("msg"),
                            session_id=session.id,
                            role="assistant",
                            content=assistant_message,
                            turn_id=turn_id,
                            created_at=now,
                        ),
                    ),
                    idempotency=new_record(
                        session_id=session.id,
                        client_request_id=request.client_request_id,
                        req_hash=req_hash,
                        status_code=200,
                        response=response.model_dump(mode="json"),
                        now=now,
                        ttl_hours=self._settings.idempotency_ttl_hours,
                    ),
                ),
                now,
            )
            logger.info(
                "turn_completed",
                extra={
                    "session_ref": log_safe_session_id(session.id),
                    "calculation_version": response.assessment.calculation_version,
                    "ai_model_id": self._ai.model_id,
                    "ai_latency_ms": ai_latency_ms,
                },
            )
            return response

    async def _extract(self, context: ExtractionContext) -> ExtractionResult | None:
        """Ask the adapter for candidates; None means it failed and we fall back."""
        try:
            return await asyncio.wait_for(
                self._ai.extract_candidates(context), self._settings.ai_timeout_seconds
            )
        except Exception:
            logger.warning("ai_extraction_failed", extra={"ai_model_id": self._ai.model_id})
            return None

    async def _generate(self, context: ResponseContext) -> str | None:
        """Ask the adapter to compose the full reply; None means use backend_text."""
        try:
            return await asyncio.wait_for(
                self._ai.generate_response(context), self._settings.ai_timeout_seconds
            )
        except Exception:
            logger.warning("ai_response_generation_failed", extra={"ai_model_id": self._ai.model_id})
            return None

    async def _phrase(self, question: Question, context: ExtractionContext) -> str:
        try:
            phrased = await asyncio.wait_for(
                self._ai.phrase_question(question, context), self._settings.ai_timeout_seconds
            )
        except Exception:
            logger.warning("ai_phrasing_failed", extra={"ai_model_id": self._ai.model_id})
            return question.text
        # Model wording may not introduce numbers or links; otherwise use approved copy.
        if not phrased or len(phrased) > MAX_QUESTION_CHARS or _UNSAFE_PHRASING_RE.search(phrased):
            return question.text
        return phrased.strip()

    async def _compose(
        self,
        context: ExtractionContext,
        outcome: ExtractionOutcome,
        question: Question | None,
        confirmed_review: bool,
        *,
        ai_failed: bool,
        calculation_summary: str | None = None,
    ) -> str:
        parts: list[str] = []
        if ai_failed:
            parts.append(AI_FALLBACK_NOTE)
        if outcome.updates:
            parts.append(_noted_text(outcome.updates))
        if confirmed_review:
            parts.append(CONFIRMED_NOTE)
        if outcome.clarify:
            parts.append(_clarify_text(outcome.clarify[0]))
        elif (
            not outcome.updates
            and not confirmed_review
            and not ai_failed
            and context.pending_field is not None
        ):
            parts.append(NO_ANSWER_NOTE)

        if outcome.clarify and question is not None and question.field == outcome.clarify[0]:
            pass  # the clarification already re-asks this question
        elif question is None:
            parts.append(DONE_MESSAGE)
        else:
            parts.append(await self._phrase(question, context))

        backend_text = " ".join(parts)

        # When not falling back, ask Bedrock to compose a natural reply from the facts.
        if not ai_failed:
            response_ctx = ResponseContext(
                backend_text=backend_text,
                next_field=question.field if question else None,
                next_question_text=question.text if question else None,
                calculation_summary=calculation_summary,
                fields_updated=list(outcome.updates.keys()),
                fields_to_clarify=list(outcome.clarify),
                recent_messages=context.recent_messages,
            )
            ai_reply = await self._generate(response_ctx)
            if ai_reply and not _UNSAFE_RESPONSE_RE.search(ai_reply) and len(ai_reply) <= MAX_QUESTION_CHARS:
                return ai_reply

        return backend_text
