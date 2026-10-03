"""Session lifecycle and bearer-token authorization."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from app.domain.profile import Profile
from app.domain.questions import next_question
from app.domain.records import ConversationState, SessionRecord, TokenRecord
from app.errors import NotFound, SessionExpired, Unauthorized
from app.repositories.base import SessionRepository
from app.security.tokens import generate_token, hash_token, new_session_id
from app.settings import Settings

Clock = Callable[[], datetime]


class SessionService:
    def __init__(self, repo: SessionRepository, settings: Settings, clock: Clock) -> None:
        self._repo = repo
        self._settings = settings
        self._clock = clock

    def _expiry(self, now: datetime) -> datetime:
        return now + timedelta(hours=self._settings.session_ttl_hours)

    async def create(self) -> tuple[SessionRecord, str]:
        """Create an anonymous session. Returns the session and the raw token (shown once)."""
        now = self._clock()
        expires_at = self._expiry(now)
        profile = Profile()
        first_question = next_question(profile)
        session = SessionRecord(
            id=new_session_id(),
            revision=0,
            turn_count=0,
            profile=profile,
            # The client shows the first question from GET /sessions/{id}; extraction
            # needs to know that is what the user's first message answers.
            conversation_state=ConversationState(
                pending_field=first_question.field if first_question else None
            ),
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )
        raw_token = generate_token()
        token = TokenRecord(
            token_hash=hash_token(raw_token),
            session_id=session.id,
            expires_at=expires_at,
            created_at=now,
        )
        await self._repo.create_session(session, token)
        return session, raw_token

    async def authorize(self, session_id: str, raw_token: str | None) -> SessionRecord:
        """Resolve the session for a request, or raise.

        * missing or unknown token          -> 401 unauthorized
        * expired token or session          -> 401 session_expired
        * valid token for another session   -> 404 not_found (do not reveal existence)
        """
        if raw_token is None:
            raise Unauthorized()
        now = self._clock()
        token = await self._repo.get_token(hash_token(raw_token))
        if token is None:
            raise Unauthorized()
        if token.session_id != session_id:
            raise NotFound()
        session = await self._repo.get_session(session_id)
        if session is None:
            raise NotFound()
        if token.expires_at <= now or session.expires_at <= now:
            raise SessionExpired()
        return session

    async def refresh_token(self, session: SessionRecord) -> tuple[str, datetime]:
        """Issue a new token, invalidate the old one, and extend the session."""
        now = self._clock()
        expires_at = self._expiry(now)
        raw_token = generate_token()
        token = TokenRecord(
            token_hash=hash_token(raw_token),
            session_id=session.id,
            expires_at=expires_at,
            created_at=now,
        )
        await self._repo.replace_tokens(session.id, token, expires_at)
        return raw_token, expires_at

    async def delete(self, session: SessionRecord) -> None:
        await self._repo.delete_session(session.id)
