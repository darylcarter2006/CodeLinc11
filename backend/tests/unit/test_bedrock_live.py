"""Live integration smoke test for BedrockAIAdapter.

Exercises all three adapter methods against the real Bedrock API:
  1. phrase_question  – rephrase the first insurance question
  2. extract_candidates – extract a field value from a user reply
  3. generate_response – compose the full assistant reply

Run with:
    cd backend
    pytest tests/unit/test_bedrock_live.py -v -s

Requirements:
  - AWS credentials with bedrock:InvokeModel permission in the target region,
    set in the .env file as AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, or via
    any standard boto3 credential chain (profile, IAM role, etc.).

The test is skipped automatically when AWS credentials are not available,
so it will never break CI.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import dotenv
import pytest

from app.ai.bedrock import BedrockAIAdapter
from app.ai.base import ExtractionContext, ResponseContext
from app.domain.questions import QUESTIONS
from app.settings import Settings

# Load .env into os.environ so boto3's credential chain picks up AWS_* vars.
# override=False means already-set env vars (e.g. from CI) take priority.
dotenv.load_dotenv(Path(__file__).parent.parent.parent / ".env", override=False)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _adapter() -> BedrockAIAdapter:
    s = Settings()
    return BedrockAIAdapter(model_id=s.bedrock_model_id, region=s.bedrock_region)


def _aws_available() -> bool:
    """Return True only when boto3 can resolve credentials (including from .env)."""
    try:
        import boto3
        session = boto3.Session()
        creds = session.get_credentials()
        return creds is not None and creds.get_frozen_credentials().access_key != ""
    except Exception:
        return False


skip_no_aws = pytest.mark.skipif(
    not _aws_available(),
    reason="No AWS credentials available — skipping live Bedrock test",
)

# First question: "How many people depend on your financial support?"
Q_DEPENDENTS = QUESTIONS[0]
# Second question: annual support need
Q_SUPPORT = QUESTIONS[1]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@skip_no_aws
def test_live_phrase_question() -> None:
    """Bedrock should return a non-empty, conversational rephrasing."""
    adapter = _adapter()
    ctx = ExtractionContext(message="", pending_field=Q_DEPENDENTS.field)

    result = asyncio.run(adapter.phrase_question(Q_DEPENDENTS, ctx))

    print(f"\n[phrase_question] raw output: {result!r}")
    # Either a rephrased string or None (FALLBACK); both are valid — we just
    # confirm it doesn't raise and, if returned, is a non-empty string.
    assert result is None or (isinstance(result, str) and len(result) > 0)


@skip_no_aws
def test_live_extract_candidates() -> None:
    """Bedrock should extract the dependents count from a plain user reply."""
    adapter = _adapter()
    ctx = ExtractionContext(
        message="My wife and two kids depend on me",
        pending_field="dependents_count",
    )

    result = asyncio.run(adapter.extract_candidates(ctx))

    print(f"\n[extract_candidates] result: {result}")
    # The model should propose at least one candidate for dependents_count.
    assert len(result.candidates) >= 1
    assert result.candidates[0].field == "dependents_count"
    # 3 dependents: wife + 2 kids
    assert result.candidates[0].value == 3


@skip_no_aws
def test_live_generate_response() -> None:
    """Bedrock should compose a short, non-empty assistant reply."""
    adapter = _adapter()
    ctx = ResponseContext(
        backend_text="Got it — 3 dependents recorded.",
        next_field=Q_SUPPORT.field,
        next_question_text=Q_SUPPORT.text,
        calculation_summary=None,
        fields_updated=["dependents_count"],
        fields_to_clarify=[],
        recent_messages=(
            ("user", "My wife and two kids depend on me"),
        ),
    )

    result = asyncio.run(adapter.generate_response(ctx))

    print(f"\n[generate_response] reply: {result!r}")
    assert result is None or (isinstance(result, str) and 0 < len(result) <= 600)
