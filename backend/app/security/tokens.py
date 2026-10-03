"""Opaque identifiers and bearer tokens.

Tokens are 32 random bytes (64 hex characters). Only a SHA-256 hash is stored, so a
leaked database does not leak usable tokens. A session ID alone is never authorization.
"""

from __future__ import annotations

import hashlib
import secrets


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(16)}"


def new_session_id() -> str:
    return f"ses_{secrets.token_hex(32)}"


def generate_token() -> str:
    return secrets.token_hex(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
