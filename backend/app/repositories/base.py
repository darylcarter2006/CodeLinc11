"""Storage interface. Services depend on this, never on a concrete database."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.profile import Profile
from app.domain.records import (
    AssessmentRecord,
    ConversationState,
    IdempotencyRecord,
    MessageRecord,
    SessionRecord,
    TokenRecord,
)


@dataclass(frozen=True)
class SessionUpdate:
    """Everything written by one user action, committed atomically.

    The commit succeeds only if the stored revision still equals ``expected_revision``;
    otherwise nothing is written and ``StaleRevision`` is raised.
    """

    expected_revision: int
    profile: Profile
    conversation_state: ConversationState
    increment_turn: bool = False
    messages: Sequence[MessageRecord] = field(default_factory=tuple)
    idempotency: IdempotencyRecord | None = None


class SessionRepository(ABC):
    @abstractmethod
    async def create_session(self, session: SessionRecord, token: TokenRecord) -> None: ...

    @abstractmethod
    async def get_session(self, session_id: str) -> SessionRecord | None: ...

    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        """Delete the session and everything linked to it."""

    @abstractmethod
    async def commit(self, session_id: str, update: SessionUpdate, now: datetime) -> SessionRecord:
        """Apply ``update`` if the revision matches; returns the new session record."""

    @abstractmethod
    async def get_token(self, token_hash: str) -> TokenRecord | None: ...

    @abstractmethod
    async def replace_tokens(
        self, session_id: str, token: TokenRecord, session_expires_at: datetime
    ) -> None:
        """Invalidate every token for the session, store ``token``, extend the session."""

    @abstractmethod
    async def get_idempotency(
        self, session_id: str, client_request_id: str
    ) -> IdempotencyRecord | None: ...

    @abstractmethod
    async def list_messages(self, session_id: str, limit: int) -> list[MessageRecord]:
        """Most recent ``limit`` messages, oldest first."""

    @abstractmethod
    async def add_assessment(self, assessment: AssessmentRecord) -> None: ...

    @abstractmethod
    async def get_latest_assessment(self, session_id: str) -> AssessmentRecord | None: ...

    @abstractmethod
    async def purge_expired(self, now: datetime) -> int:
        """Delete expired sessions and idempotency records; returns sessions removed."""

    @abstractmethod
    async def ping(self) -> bool:
        """Readiness check: can the store serve requests?"""

    @asynccontextmanager
    async def session_lock(self, session_id: str) -> AsyncIterator[None]:
        """Serialize work on one session where the backend supports it.

        The default is a no-op; correctness then relies on the revision check in
        ``commit`` (plus a pending idempotency record in a shared database).
        """
        yield
