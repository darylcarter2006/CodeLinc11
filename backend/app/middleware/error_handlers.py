"""Map every error to the canonical envelope: {"error": {"code", "message", ...}}."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import AppError
from app.middleware.request_context import current_request_id

_HTTP_CODES = {
    401: "unauthorized",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
}


def error_response(status_code: int, code: str, message: str, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message, "request_id": current_request_id()}
    body.update({key: value for key, value in extra.items() if value is not None})
    return JSONResponse(status_code=status_code, content={"error": body})


def _validation_details(exc: RequestValidationError) -> list[dict[str, Any]]:
    # Never echo the submitted input back; only where and why it failed.
    return [{"loc": list(err.get("loc", ())), "msg": err.get("msg", "")} for err in exc.errors()]


async def _app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(exc.status_code, exc.code, exc.message, **exc.extra)


async def _request_validation(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return error_response(
        422,
        "validation_error",
        "The request contains invalid fields.",
        details=_validation_details(exc),
    )


async def _http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _HTTP_CODES.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return error_response(exc.status_code, code, message)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _request_validation)
    app.add_exception_handler(StarletteHTTPException, _http_exception)
    # Unexpected exceptions are turned into 500 envelopes by RequestContextMiddleware.
