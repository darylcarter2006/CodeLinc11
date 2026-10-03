"""Direct profile edits (PATCH) and the shared profile response."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.calculators.registry import get_policy
from app.contracts.requests import ProfilePatchRequest, ProfileUpdates
from app.contracts.responses import ProfileResponse
from app.domain.profile import Profile, ProfileValue, Source
from app.domain.questions import next_question
from app.domain.records import ConversationState, SessionRecord
from app.errors import NotFound, StaleRevision, ValidationFailed
from app.repositories.base import SessionRepository, SessionUpdate
from app.services.idempotency import find_replay, new_record, request_hash
from app.services.presenters import to_next_question, to_preview
from app.services.sessions import Clock
from app.settings import Settings


async def load_for_update(
    repo: SessionRepository, session_id: str, expected_revision: int
) -> SessionRecord:
    """Re-read the session under the lock and fail fast on a stale revision."""
    session = await repo.get_session(session_id)
    if session is None:
        raise NotFound()
    if session.revision != expected_revision:
        raise StaleRevision(current_revision=session.revision)
    return session


def build_profile_response(session_id: str, revision: int, profile: Profile) -> ProfileResponse:
    return ProfileResponse(
        session_id=session_id,
        revision=revision,
        profile=profile,
        next_question=to_next_question(next_question(profile)),
        assessment=to_preview(get_policy().calculate(profile)),
    )


def apply_user_edits(profile: Profile, updates: ProfileUpdates, confirm: list[str]) -> Profile:
    """Edits are user-entered, so they are recorded as ``edited`` and confirmed."""
    changes: dict[str, Any] = {}
    for name in updates.model_fields_set:
        if name == "assumption_flags":
            if updates.assumption_flags is None:
                continue
            flags = updates.assumption_flags
            changes[name] = profile.assumption_flags.model_copy(
                update={key: getattr(flags, key) for key in flags.model_fields_set}
            )
            continue
        changes[name] = ProfileValue[Any](
            value=getattr(updates, name), source=Source.EDITED, confirmed=True
        )
    for name in confirm:
        if name in changes:
            continue
        current = profile.field(name)
        if current is None:
            raise ValidationFailed(f"Cannot confirm {name}: it has not been answered yet.")
        changes[name] = current.model_copy(update={"confirmed": True})
    try:
        return profile.with_fields(changes)
    except ValidationError as exc:
        raise ValidationFailed(
            details=[{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        ) from None


class ProfileService:
    def __init__(self, repo: SessionRepository, settings: Settings, clock: Clock) -> None:
        self._repo = repo
        self._settings = settings
        self._clock = clock

    async def patch(self, session: SessionRecord, request: ProfilePatchRequest) -> ProfileResponse:
        req_hash = request_hash("profile_patch", request.model_dump(mode="json"))
        async with self._repo.session_lock(session.id):
            replay = await find_replay(self._repo, session.id, request.client_request_id, req_hash)
            if replay is not None:
                return ProfileResponse.model_validate(replay.response)

            session = await load_for_update(self._repo, session.id, request.expected_revision)
            profile = apply_user_edits(session.profile, request.updates, list(request.confirm))
            question = next_question(profile)
            response = build_profile_response(session.id, request.expected_revision + 1, profile)
            now = self._clock()
            await self._repo.commit(
                session.id,
                SessionUpdate(
                    expected_revision=request.expected_revision,
                    profile=profile,
                    conversation_state=ConversationState(
                        pending_field=question.field if question else None
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
            return response
