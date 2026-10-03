"""Shared route dependencies: the service container and the authorized session."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.container import Container
from app.contracts.responses import ErrorResponse
from app.domain.records import SessionRecord

_bearer = HTTPBearer(auto_error=False, description="Token returned by POST /v1/sessions")


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


async def get_authorized_session(
    container: ContainerDep,
    session_id: Annotated[str, Path(min_length=1, max_length=128)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> SessionRecord:
    token = credentials.credentials if credentials is not None else None
    return await container.sessions.authorize(session_id, token)


SessionDep = Annotated[SessionRecord, Depends(get_authorized_session)]


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI documentation for the error envelope on the given status codes."""
    return {code: {"model": ErrorResponse} for code in codes}


AUTH_ERRORS = error_responses(401, 404)
