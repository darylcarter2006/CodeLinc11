"""Unit tests for BedrockAIAdapter.

All AWS calls are mocked — no real credentials or network access needed.
Tests verify:
  * Successful extraction parses and validates JSON from the model.
  * Unknown-fields returned by the model are silently dropped.
  * Malformed JSON from the model returns an empty ExtractionResult (graceful fallback).
  * phrase_question returns None when the model says FALLBACK.
  * phrase_question returns the rephrased text when the model returns valid copy.
  * build_ai_adapter wires BedrockAIAdapter when ai_provider == "bedrock".
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.ai.base import ExtractionContext, ExtractionResult
from app.ai.bedrock import BedrockAIAdapter
from app.domain.questions import QUESTIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_adapter() -> BedrockAIAdapter:
    return BedrockAIAdapter(
        model_id="amazon.nova-lite-v1:0",
        region="us-east-1",
    )


def _converse_response(text: str) -> dict[str, Any]:
    """Minimal Bedrock Converse response envelope."""
    return {
        "output": {
            "message": {
                "content": [{"text": text}]
            }
        }
    }


def _extraction_context(message: str, field: str = "annual_support_need") -> ExtractionContext:
    return ExtractionContext(message=message, pending_field=field)


# ---------------------------------------------------------------------------
# extract_candidates
# ---------------------------------------------------------------------------

def test_extract_valid_candidate() -> None:
    payload = json.dumps({
        "candidates": [
            {
                "field": "annual_support_need",
                "value": 80000,
                "unknown": False,
                "evidence": "80k a year",
                "ambiguous": False,
                "is_correction": False,
            }
        ]
    })
    adapter = _make_adapter()
    with patch.object(adapter, "_client") as mock_client:
        mock_client.converse.return_value = _converse_response(payload)
        result = asyncio.run(
            adapter.extract_candidates(_extraction_context("We spend 80k a year"))
        )
    assert len(result.candidates) == 1
    assert result.candidates[0].value == 80000
    assert result.candidates[0].field == "annual_support_need"


def test_extract_unknown_fields_are_dropped() -> None:
    """The model must not inject arbitrary field names."""
    payload = json.dumps({
        "candidates": [
            {
                "field": "annual_support_need",
                "value": 50000,
                "unknown": False,
                "evidence": "50k",
                "ambiguous": False,
                "is_correction": False,
            },
            {
                "field": "INVENTED_FIELD",
                "value": 999,
                "unknown": False,
                "evidence": "999",
                "ambiguous": False,
                "is_correction": False,
            },
        ]
    })
    adapter = _make_adapter()
    with patch.object(adapter, "_client") as mock_client:
        mock_client.converse.return_value = _converse_response(payload)
        result = asyncio.run(
            adapter.extract_candidates(_extraction_context("I earn 50k"))
        )
    assert len(result.candidates) == 1
    assert result.candidates[0].field == "annual_support_need"


def test_extract_malformed_json_returns_empty() -> None:
    """If Bedrock returns garbage, we get an empty result, not an exception."""
    adapter = _make_adapter()
    with patch.object(adapter, "_client") as mock_client:
        mock_client.converse.return_value = _converse_response("not valid json at all")
        result = asyncio.run(
            adapter.extract_candidates(_extraction_context("something"))
        )
    assert result == ExtractionResult()


def test_extract_empty_candidates() -> None:
    payload = json.dumps({"candidates": []})
    adapter = _make_adapter()
    with patch.object(adapter, "_client") as mock_client:
        mock_client.converse.return_value = _converse_response(payload)
        result = asyncio.run(
            adapter.extract_candidates(_extraction_context("hello there"))
        )
    assert result.candidates == []


def test_extract_unknown_value() -> None:
    payload = json.dumps({
        "candidates": [
            {
                "field": "annual_support_need",
                "value": None,
                "unknown": True,
                "evidence": "not sure",
                "ambiguous": False,
                "is_correction": False,
            }
        ]
    })
    adapter = _make_adapter()
    with patch.object(adapter, "_client") as mock_client:
        mock_client.converse.return_value = _converse_response(payload)
        result = asyncio.run(
            adapter.extract_candidates(_extraction_context("I'm not sure"))
        )
    assert result.candidates[0].unknown is True
    assert result.candidates[0].value is None


# ---------------------------------------------------------------------------
# phrase_question
# ---------------------------------------------------------------------------

def test_phrase_question_returns_rephrased_text() -> None:
    adapter = _make_adapter()
    context = ExtractionContext(message="", pending_field=None)
    with patch.object(adapter, "_client") as mock_client:
        mock_client.converse.return_value = _converse_response(
            "How many people rely on your income?"
        )
        result = asyncio.run(adapter.phrase_question(QUESTIONS[0], context))
    assert result == "How many people rely on your income?"


def test_phrase_question_fallback_returns_none() -> None:
    adapter = _make_adapter()
    context = ExtractionContext(message="", pending_field=None)
    with patch.object(adapter, "_client") as mock_client:
        mock_client.converse.return_value = _converse_response("FALLBACK")
        result = asyncio.run(adapter.phrase_question(QUESTIONS[0], context))
    assert result is None


def test_phrase_question_empty_response_returns_none() -> None:
    adapter = _make_adapter()
    context = ExtractionContext(message="", pending_field=None)
    with patch.object(adapter, "_client") as mock_client:
        mock_client.converse.return_value = _converse_response("")
        result = asyncio.run(adapter.phrase_question(QUESTIONS[0], context))
    assert result is None


# ---------------------------------------------------------------------------
# container wiring
# ---------------------------------------------------------------------------

def test_build_ai_adapter_returns_bedrock_when_configured() -> None:
    from app.container import build_ai_adapter
    from app.settings import Settings

    settings = Settings(
        ai_provider="bedrock",
        bedrock_model_id="amazon.nova-lite-v1:0",
        bedrock_region="us-east-1",
    )
    adapter = build_ai_adapter(settings)
    assert isinstance(adapter, BedrockAIAdapter)
    assert adapter.model_id == "amazon.nova-lite-v1:0"


def test_build_ai_adapter_returns_stub_by_default() -> None:
    from app.ai.stub import StubAIAdapter
    from app.container import build_ai_adapter
    from app.settings import Settings

    adapter = build_ai_adapter(Settings(ai_provider="stub"))
    assert isinstance(adapter, StubAIAdapter)
