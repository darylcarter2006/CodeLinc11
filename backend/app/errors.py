"""Application errors. Each maps to one stable `code` in the canonical error envelope."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    code: str = "internal_error"
    status_code: int = 500
    default_message: str = "Something went wrong. Please try again."

    def __init__(self, message: str | None = None, **extra: Any) -> None:
        self.message = message or self.default_message
        self.extra = extra
        super().__init__(self.message)


class ValidationFailed(AppError):
    code = "validation_error"
    status_code = 422
    default_message = "The request contains invalid fields."


class Unauthorized(AppError):
    code = "unauthorized"
    status_code = 401
    default_message = "A valid bearer token is required."


class SessionExpired(AppError):
    code = "session_expired"
    status_code = 401
    default_message = "This session has expired. Please start a new session."


class NotFound(AppError):
    # Also used when a valid token is presented for someone else's session,
    # so callers cannot probe which session IDs exist.
    code = "not_found"
    status_code = 404
    default_message = "The requested resource was not found."


class StaleRevision(AppError):
    code = "stale_revision"
    status_code = 409
    default_message = "The session has been updated since your request was formed."

    def __init__(self, current_revision: int) -> None:
        super().__init__(current_revision=current_revision)
        self.current_revision = current_revision


class DuplicateRequest(AppError):
    code = "duplicate_request"
    status_code = 409
    default_message = "This client_request_id was already used with a different payload."


class PayloadTooLarge(AppError):
    code = "payload_too_large"
    status_code = 413
    default_message = "The request body is too large."


class TurnLimitExceeded(AppError):
    code = "turn_limit_exceeded"
    status_code = 429
    default_message = (
        "This session has reached its message limit. "
        "You can still edit your answers directly or start a new session."
    )


class RateLimited(AppError):
    code = "rate_limited"
    status_code = 429
    default_message = "That's a lot of requests at once. Please try again in a minute."


class AIUnavailable(AppError):
    # The front end treats 503 as "no live AI" and switches to its local fallbacks.
    code = "ai_unavailable"
    status_code = 503
    default_message = "Live answers aren't available right now."


class AIFailed(AppError):
    code = "ai_failed"
    status_code = 502
    default_message = "The answer couldn't be completed. Please try again."


class AuthNotConfigured(AppError):
    code = "auth_unavailable"
    status_code = 503
    default_message = "Google sign-in isn't set up on this server."


class InvalidCredential(AppError):
    code = "invalid_credential"
    status_code = 401
    default_message = "Google sign-in couldn't be verified. Please try again."


class AuthProviderUnreachable(AppError):
    code = "auth_provider_unreachable"
    status_code = 503
    default_message = "We couldn't reach Google to verify your sign-in. Please try again."


class EmailInUse(AppError):
    code = "email_taken"
    status_code = 409
    default_message = "An account with this email already exists. Log in instead."


class InvalidLogin(AppError):
    code = "invalid_login"
    status_code = 401
    # The same message whether the email or the password was wrong.
    default_message = "That email and password don't match. Try again, or reset your password."


class WeakPassword(AppError):
    code = "weak_password"
    status_code = 422
    default_message = "Choose a different password."


class PasswordNotSet(AppError):
    code = "password_not_set"
    status_code = 409
    default_message = (
        'This account signs in with Google. To add a password, use "Forgot password?" on the '
        "log-in page."
    )


class ResetLinkInvalid(AppError):
    code = "reset_link_invalid"
    status_code = 400
    default_message = "This reset link has expired or was already used. Request a new one."


class ResetUnavailable(AppError):
    code = "reset_unavailable"
    status_code = 503
    default_message = "Password reset by email isn't set up on this server yet."


class AIUnverified(AppError):
    code = "ai_unverified"
    status_code = 502
    default_message = (
        "The live answer used numbers that don't match your estimate, so it wasn't shown."
    )
