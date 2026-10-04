from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import ContainerDep, error_responses
from app.contracts.auth import (
    ChangePasswordRequest,
    GoogleSignInRequest,
    LogInRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    SignInResponse,
    SignUpRequest,
    UserOut,
)
from app.domain.users import UserRecord
from app.errors import Unauthorized

router = APIRouter(prefix="/auth", tags=["auth"])

_bearer = HTTPBearer(auto_error=False, description="Token returned by sign-up or log-in")
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def user_out(user: UserRecord) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        given_name=user.given_name,
        picture=user.picture,
        has_password=user.password_hash is not None,
    )


def _signed_in(result: tuple[UserRecord, str, datetime]) -> SignInResponse:
    user, token, expires_at = result
    return SignInResponse(access_token=token, expires_at=expires_at, user=user_out(user))


def rate_limit(request: Request, container: ContainerDep) -> None:
    client = request.client.host if request.client else "unknown"
    container.auth_limiter.check(client)


def reset_rate_limit(request: Request, container: ContainerDep) -> None:
    client = request.client.host if request.client else "unknown"
    container.reset_ip_limiter.check(client)


async def current_user(container: ContainerDep, credentials: BearerDep) -> tuple[UserRecord, str]:
    """The signed-in user and their raw token; 401 without a valid one."""
    if credentials is None:
        raise Unauthorized()
    return await container.accounts.authorize(credentials.credentials), credentials.credentials


CurrentUser = Annotated[tuple[UserRecord, str], Depends(current_user)]


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=SignInResponse,
    responses=error_responses(409, 422, 429),
    dependencies=[Depends(rate_limit)],
)
async def sign_up(body: SignUpRequest, container: ContainerDep) -> SignInResponse:
    """Create an account with an email and password, and sign in."""
    return _signed_in(await container.accounts.sign_up(body.name, body.email, body.password))


@router.post(
    "/login",
    response_model=SignInResponse,
    responses=error_responses(401, 422, 429),
    dependencies=[Depends(rate_limit)],
)
async def log_in(body: LogInRequest, container: ContainerDep) -> SignInResponse:
    return _signed_in(await container.accounts.log_in(body.email, body.password))


@router.post(
    "/google",
    response_model=SignInResponse,
    responses=error_responses(401, 422, 429, 503),
    dependencies=[Depends(rate_limit)],
)
async def sign_in_with_google(body: GoogleSignInRequest, container: ContainerDep) -> SignInResponse:
    """Exchange a Google ID token for our own account token."""
    return _signed_in(await container.accounts.sign_in_with_google(body.credential))


@router.get("/me", response_model=UserOut, responses=error_responses(401))
async def me(signed_in: CurrentUser) -> UserOut:
    return user_out(signed_in[0])


@router.post(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 409, 422, 429),
    dependencies=[Depends(rate_limit)],
)
async def change_password(
    body: ChangePasswordRequest, signed_in: CurrentUser, container: ContainerDep
) -> Response:
    """Change the password. Other devices are signed out; this one stays signed in."""
    user, token = signed_in
    await container.accounts.change_password(user, token, body.current_password, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/password-reset/request",
    status_code=status.HTTP_202_ACCEPTED,
    responses=error_responses(422, 429, 503),
    dependencies=[Depends(reset_rate_limit)],
)
async def request_password_reset(
    body: PasswordResetRequest, container: ContainerDep, background: BackgroundTasks
) -> Response:
    """Email a reset link if the address has an account. The reply is the same either way."""
    message = await container.accounts.request_password_reset(body.email)
    if message is not None:
        background.add_task(container.email.send, message)
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post(
    "/password-reset/confirm",
    response_model=SignInResponse,
    responses=error_responses(400, 422, 429),
    dependencies=[Depends(rate_limit)],
)
async def confirm_password_reset(
    body: PasswordResetConfirm, container: ContainerDep
) -> SignInResponse:
    """Set a new password from a reset link, sign out everywhere else, and sign in."""
    return _signed_in(
        await container.accounts.confirm_password_reset(body.token, body.new_password)
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(401))
async def logout(signed_in: CurrentUser, container: ContainerDep) -> Response:
    await container.accounts.sign_out(signed_in[1])
    return Response(status_code=status.HTTP_204_NO_CONTENT)
