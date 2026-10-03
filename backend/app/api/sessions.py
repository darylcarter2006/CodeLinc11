from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import AUTH_ERRORS, ContainerDep, SessionDep
from app.contracts.requests import CreateSessionRequest
from app.contracts.responses import SessionCreatedResponse, SessionResponse, TokenResponse
from app.services.profiles import build_profile_response

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SessionCreatedResponse)
async def create_session(
    container: ContainerDep, body: CreateSessionRequest | None = None
) -> SessionCreatedResponse:
    session, token = await container.sessions.create()
    return SessionCreatedResponse(
        session_id=session.id,
        revision=session.revision,
        access_token=token,
        expires_at=session.expires_at,
    )


@router.get("/{session_id}", response_model=SessionResponse, responses=AUTH_ERRORS)
async def get_session(session: SessionDep, container: ContainerDep) -> SessionResponse:
    base = build_profile_response(session.id, session.revision, session.profile)
    return SessionResponse(
        **base.model_dump(),
        turn_count=session.turn_count,
        turn_limit=container.settings.session_turn_limit,
        expires_at=session.expires_at,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT, responses=AUTH_ERRORS)
async def delete_session(session: SessionDep, container: ContainerDep) -> Response:
    await container.sessions.delete(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{session_id}/token", response_model=TokenResponse, responses=AUTH_ERRORS)
async def refresh_token(session: SessionDep, container: ContainerDep) -> TokenResponse:
    token, expires_at = await container.sessions.refresh_token(session)
    return TokenResponse(access_token=token, expires_at=expires_at)
