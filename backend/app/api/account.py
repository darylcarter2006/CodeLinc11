"""The signed-in person's saved state, so it follows them to any device."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from app.api.auth import CurrentUser
from app.api.deps import ContainerDep, error_responses
from app.contracts.auth import DeleteAccountRequest
from app.contracts.profile_state import ProfileState, ProfileStateOut
from app.security.redaction import log_safe_session_id

router = APIRouter(prefix="/account", tags=["account"])
logger = logging.getLogger(__name__)


@router.get("/profile", response_model=ProfileStateOut, responses=error_responses(401))
async def get_profile(signed_in: CurrentUser, container: ContainerDep) -> ProfileStateOut:
    user = signed_in[0]
    stored = await container.profile_states.get(user.id)
    if stored is None:
        return ProfileStateOut(state=None, updated_at=None)
    data, updated_at = stored
    try:
        state = ProfileState.model_validate(data)
    except ValueError:
        # Saved under older rules; the person starts over rather than seeing broken data.
        logger.warning(
            "profile_state_unreadable", extra={"session_ref": log_safe_session_id(user.id)}
        )
        return ProfileStateOut(state=None, updated_at=None)
    return ProfileStateOut(state=state, updated_at=updated_at)


@router.put("/profile", response_model=ProfileStateOut, responses=error_responses(401, 413, 422))
async def put_profile(
    body: ProfileState, signed_in: CurrentUser, container: ContainerDep
) -> ProfileStateOut:
    """Replace the saved state with this one (the browser always sends all of it)."""
    now = container.clock()
    await container.profile_states.put(signed_in[0].id, body.model_dump(mode="json"), now)
    return ProfileStateOut(state=body, updated_at=now)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(401, 422))
async def delete_account(
    body: DeleteAccountRequest, signed_in: CurrentUser, container: ContainerDep
) -> Response:
    """Delete the account and everything kept for it. Needs the password if it has one."""
    user = signed_in[0]
    container.accounts.confirm_password(user, body.password)
    await container.personal_data.delete_account(user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
