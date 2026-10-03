from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import ContainerDep, error_responses
from app.contracts.auth import GoogleSignInRequest, SignInResponse, UserOut
from app.domain.users import UserRecord

router = APIRouter(prefix="/auth", tags=["auth"])

_bearer = HTTPBearer(auto_error=False, description="Token returned by POST /v1/auth/google")
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def _user_out(user: UserRecord) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        given_name=user.given_name,
        picture=user.picture,
    )


def rate_limit(request: Request, container: ContainerDep) -> None:
    client = request.client.host if request.client else "unknown"
    container.auth_limiter.check(client)


@router.post(
    "/google",
    response_model=SignInResponse,
    responses=error_responses(401, 422, 429, 503),
    dependencies=[Depends(rate_limit)],
)
async def sign_in_with_google(body: GoogleSignInRequest, container: ContainerDep) -> SignInResponse:
    """Exchange a Google ID token for our own account token."""
    user, token, expires_at = await container.accounts.sign_in_with_google(body.credential)
    return SignInResponse(access_token=token, expires_at=expires_at, user=_user_out(user))


@router.get("/me", response_model=UserOut, responses=error_responses(401))
async def me(container: ContainerDep, credentials: BearerDep) -> UserOut:
    token = credentials.credentials if credentials else None
    return _user_out(await container.accounts.authorize(token))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(401))
async def logout(container: ContainerDep, credentials: BearerDep) -> Response:
    token = credentials.credentials if credentials else None
    await container.accounts.authorize(token)
    assert token is not None  # authorize() rejects a missing token
    await container.accounts.sign_out(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
