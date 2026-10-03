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
