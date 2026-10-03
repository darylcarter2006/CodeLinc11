"""Replay-safe writes keyed by (session_id, client_request_id)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

from app.domain.records import IdempotencyRecord
from app.errors import DuplicateRequest
from app.repositories.base import SessionRepository


def request_hash(operation: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps({"op": operation, "body": payload}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def find_replay(
    repo: SessionRepository, session_id: str, client_request_id: str, req_hash: str
) -> IdempotencyRecord | None:
    """Return the stored record for an identical retry; raise if the payload differs."""
    record = await repo.get_idempotency(session_id, client_request_id)
    if record is None:
        return None
    if record.request_hash != req_hash:
        raise DuplicateRequest()
    return record


def new_record(
    *,
    session_id: str,
    client_request_id: str,
    req_hash: str,
    status_code: int,
    response: dict[str, Any],
    now: datetime,
    ttl_hours: int,
) -> IdempotencyRecord:
    return IdempotencyRecord(
        session_id=session_id,
        client_request_id=client_request_id,
        request_hash=req_hash,
        status_code=status_code,
        response=response,
        created_at=now,
        expires_at=now + timedelta(hours=ttl_hours),
    )
