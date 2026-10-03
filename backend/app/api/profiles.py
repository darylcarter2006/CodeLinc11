from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AUTH_ERRORS, ContainerDep, SessionDep, error_responses
from app.contracts.requests import ProfilePatchRequest
from app.contracts.responses import ProfileResponse
from app.services.profiles import build_profile_response

router = APIRouter(prefix="/sessions/{session_id}/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse, responses=AUTH_ERRORS)
async def get_profile(session: SessionDep) -> ProfileResponse:
    return build_profile_response(session.id, session.revision, session.profile)


@router.patch(
    "",
    response_model=ProfileResponse,
    responses={**AUTH_ERRORS, **error_responses(409, 422)},
)
async def patch_profile(
    body: ProfilePatchRequest, session: SessionDep, container: ContainerDep
) -> ProfileResponse:
    return await container.profiles.patch(session, body)
