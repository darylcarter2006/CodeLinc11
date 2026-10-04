"""Security headers on every API response (pure ASGI, so it also covers errors and 413s)."""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_COMMON: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]
# The API answers JSON only: nothing should render, frame, or be cached by a shared proxy.
_API = [
    (b"referrer-policy", b"no-referrer"),
    (b"cache-control", b"no-store"),
    (b"cross-origin-resource-policy", b"cross-origin"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
]
# The interactive docs page loads FastAPI's Swagger bundle, so it can't use the strict policy.
_DOCS_PATHS = ("/docs", "/openapi.json")
# The front end, when this server serves it (STATIC_DIR): the same policy as customHttp.yml.
_SITE_CSP = (
    b"default-src 'self'; script-src 'self' https://accounts.google.com/gsi/client; "
    b"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com "
    b"https://accounts.google.com/gsi/style; font-src 'self' https://fonts.gstatic.com; "
    b"img-src 'self' data: https://*.googleusercontent.com; "
    b"connect-src 'self' https://accounts.google.com/gsi/; "
    b"frame-src https://accounts.google.com/gsi/; "
    b"frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
)
_SITE = [
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"cross-origin-opener-policy", b"same-origin-allow-popups"),
    (b"content-security-policy", _SITE_CSP),
]
_HSTS = (b"strict-transport-security", b"max-age=31536000; includeSubDomains")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path", ""))
        extra = list(_COMMON)
        if path.startswith("/v1"):
            extra += _API
        elif path.startswith(_DOCS_PATHS):
            extra += [h for h in _API if h[0] != b"content-security-policy"]
        else:
            extra += _SITE
            # Built files have content hashes in their names, so they never change.
            cache = (
                b"public, max-age=31536000, immutable"
                if path.startswith("/assets/")
                else b"no-cache"
            )
            extra.append((b"cache-control", cache))
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
