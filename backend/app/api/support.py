from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import ContainerDep, error_responses
from app.contracts.support import CallbackRequestIn, CallbackRequestOut
from app.errors import AppError

router = APIRouter(prefix="/support", tags=["support"])

_bearer = HTTPBearer(auto_error=False)


def rate_limit(request: Request, container: ContainerDep) -> None:
    client = request.client.host if request.client else "unknown"
    container.support_limiter.check(client)
    container.support_global_limiter.check("all-clients")


@router.post(
    "/callback-requests",
    status_code=status.HTTP_201_CREATED,
    response_model=CallbackRequestOut,
    responses=error_responses(422, 429),
    dependencies=[Depends(rate_limit)],
)
async def request_callback(
    body: CallbackRequestIn,
    container: ContainerDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CallbackRequestOut:
    """Ask a licensed representative to follow up. Signing in is optional."""
    user_id = None
    if credentials is not None:
        try:
            user_id = (await container.accounts.authorize(credentials.credentials)).id
        except AppError:
            user_id = None  # an expired or unknown token doesn't block the request
    return CallbackRequestOut(id=await container.support.request_callback(body, user_id))
