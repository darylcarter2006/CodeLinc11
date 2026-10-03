"""In-process repository for local development, tests and demos without a database.

Single-process only: data is lost on restart and is not shared between instances.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from app.domain.records import (
    AssessmentRecord,
    IdempotencyRecord,
    MessageRecord,
    SessionRecord,
    TokenRecord,
)
from app.errors import NotFound, StaleRevision
from app.repositories.base import SessionRepository, SessionUpdate


class InMemorySessionRepository(SessionRepository):
    def __init__(self, max_messages_per_session: int = 20) -> None:
        self._max_messages = max_messages_per_session
        self._sessions: dict[str, SessionRecord] = {}
        self._tokens: dict[str, TokenRecord] = {}
        self._messages: dict[str, list[MessageRecord]] = defaultdict(list)
        self._assessments: dict[str, list[AssessmentRecord]] = defaultdict(list)
        self._idempotency: dict[tuple[str, str], IdempotencyRecord] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def create_session(self, session: SessionRecord, token: TokenRecord) -> None:
        self._sessions[session.id] = session
        self._tokens[token.token_hash] = token

    async def get_session(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    async def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._messages.pop(session_id, None)
        self._assessments.pop(session_id, None)
        self._locks.pop(session_id, None)
        for token_hash in [h for h, t in self._tokens.items() if t.session_id == session_id]:
            del self._tokens[token_hash]
        for key in [k for k in self._idempotency if k[0] == session_id]:
            del self._idempotency[key]

    async def commit(self, session_id: str, update: SessionUpdate, now: datetime) -> SessionRecord:
        current = self._sessions.get(session_id)
        if current is None:
            raise NotFound()
        if current.revision != update.expected_revision:
            raise StaleRevision(current_revision=current.revision)

        updated = current.model_copy(
            update={
                "revision": current.revision + 1,
                "turn_count": current.turn_count + (1 if update.increment_turn else 0),
                "profile": update.profile,
                "conversation_state": update.conversation_state,
                "updated_at": now,
            }
        )
        # Nothing above can fail after this point, so the writes below are all-or-nothing.
        self._sessions[session_id] = updated
        if update.messages:
            history = self._messages[session_id]
            history.extend(update.messages)
            del history[: max(0, len(history) - self._max_messages)]
        if update.idempotency is not None:
            key = (session_id, update.idempotency.client_request_id)
            self._idempotency[key] = update.idempotency
        return updated

    async def get_token(self, token_hash: str) -> TokenRecord | None:
        return self._tokens.get(token_hash)

    async def replace_tokens(
        self, session_id: str, token: TokenRecord, session_expires_at: datetime
    ) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            raise NotFound()
        for token_hash in [h for h, t in self._tokens.items() if t.session_id == session_id]:
            del self._tokens[token_hash]
        self._tokens[token.token_hash] = token
        self._sessions[session_id] = session.model_copy(update={"expires_at": session_expires_at})

    async def get_idempotency(
        self, session_id: str, client_request_id: str
    ) -> IdempotencyRecord | None:
        return self._idempotency.get((session_id, client_request_id))

    async def list_messages(self, session_id: str, limit: int) -> list[MessageRecord]:
        if limit <= 0:
            return []
        return list(self._messages.get(session_id, [])[-limit:])

    async def add_assessment(self, assessment: AssessmentRecord) -> None:
        self._assessments[assessment.session_id].append(assessment)

    async def get_latest_assessment(self, session_id: str) -> AssessmentRecord | None:
        history = self._assessments.get(session_id)
        return history[-1] if history else None

    async def purge_expired(self, now: datetime) -> int:
        expired = [sid for sid, s in self._sessions.items() if s.expires_at <= now]
        for session_id in expired:
            await self.delete_session(session_id)
        for key in [k for k, r in self._idempotency.items() if r.expires_at <= now]:
            del self._idempotency[key]
        return len(expired)

    async def ping(self) -> bool:
        return True

    @asynccontextmanager
    async def session_lock(self, session_id: str) -> AsyncIterator[None]:
        async with self._locks[session_id]:
            yield
