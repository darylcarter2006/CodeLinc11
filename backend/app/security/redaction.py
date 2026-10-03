"""Helpers that keep sensitive values out of logs."""

from __future__ import annotations

import hashlib


def log_safe_session_id(session_id: str) -> str:
    """A short, stable, non-reversible handle for correlating log lines."""
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:12]
