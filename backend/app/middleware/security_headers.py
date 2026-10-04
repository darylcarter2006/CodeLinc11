"""Security headers on every API response (pure ASGI, so it also covers errors and 413s)."""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# JSON only: nothing here should ever render, frame, or be cached by a shared proxy.
_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cache-control", b"no-store"),
    (b"cross-origin-resource-policy", b"cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]
_API_CSP = (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")
# The interactive docs page loads FastAPI's Swagger bundle, so it can't use the strict policy.
_DOCS_PATHS = ("/docs", "/openapi.json")
_HSTS = (b"strict-transport-security", b"max-age=31536000; includeSubDomains")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        extra = list(_HEADERS)
        if not str(scope.get("path", "")).startswith(_DOCS_PATHS):
            extra.append(_API_CSP)
        if self.hsts:
            extra.append(_HSTS)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                present = {name.lower() for name, _ in message.get("headers", [])}
                message["headers"] = list(message.get("headers", [])) + [
                    (name, value) for name, value in extra if name not in present
                ]
            await send(message)

        await self.app(scope, receive, send_with_headers)
