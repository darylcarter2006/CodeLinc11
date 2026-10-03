"""Request ID, body-size limit and access logging, as one pure ASGI middleware.

Pure ASGI (rather than BaseHTTPMiddleware) so the body can be checked before the app
reads it, and so streaming responses are not buffered.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import time
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app.access")

REQUEST_ID_HEADER = "x-request-id"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

PAYLOAD_TOO_LARGE = ("payload_too_large", "The request body is too large.")
INTERNAL_ERROR = ("internal_error", "Something went wrong. Please try again.")

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    return request_id_var.get()


def _new_request_id() -> str:
    return f"req_{secrets.token_hex(12)}"


def _endpoint_template(scope: Scope) -> str:
    """The path with parameter values replaced by their names.

    Never log the raw path: it contains session IDs.
    """
    path: str = scope.get("path", "")
    params: dict[str, object] = scope.get("path_params") or {}
    if not params:
        return path if scope.get("route") is not None else "unmatched"
    for name, value in params.items():
        path = path.replace(f"/{value}", f"/{{{name}}}", 1)
    return path


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(REQUEST_ID_HEADER.encode(), b"").decode("latin-1")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else _new_request_id()
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            body = await self._read_body(receive)
            if body is None:
                await self._send_error(send_with_id, 413, PAYLOAD_TOO_LARGE, request_id)
                return

            sent = False

            async def replay() -> Message:
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            try:
                await self.app(scope, replay, send_with_id)
            except Exception:
                # Handled here rather than by Starlette's outermost error middleware so the
                # 500 still carries the request ID and the canonical envelope.
                logger.exception("unhandled_error", extra={"request_id": request_id})
                if response_started:
                    raise
                await self._send_error(send_with_id, 500, INTERNAL_ERROR, request_id)
        finally:
            logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": scope.get("method"),
                    "endpoint": _endpoint_template(scope),
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            request_id_var.reset(token)

    async def _read_body(self, receive: Receive) -> bytes | None:
        """Read the whole body, or return None as soon as it exceeds the limit."""
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                break
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_body_bytes:
                return None
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        return b"".join(chunks)

    async def _send_error(
        self, send: Send, status: int, error: tuple[str, str], request_id: str
    ) -> None:
        code, message = error
        body = json.dumps(
            {"error": {"code": code, "message": message, "request_id": request_id}}
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
