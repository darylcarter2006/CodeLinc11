"""Scriptable stand-in for a real model provider."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.ai.base import (
    AIAdapter,
    ChatMessage,
    ExtractionContext,
    ExtractionResult,
    ModelTier,
)
from app.domain.questions import Question


class FakeModel(AIAdapter):
    """Returns a fixed reply (or raises a fixed error) and records what it was sent."""

    model_id = "fake"

    def __init__(
        self,
        reply: str = "",
        chunks: list[str] | None = None,
        error: Exception | None = None,
        fail_after_chunks: int | None = None,
    ) -> None:
        self.reply = reply
        self.chunks = chunks if chunks is not None else [reply]
        self.error = error
        self.fail_after_chunks = fail_after_chunks
        self.calls: list[tuple[str, list[ChatMessage], ModelTier]] = []

    async def extract_candidates(self, context: ExtractionContext) -> ExtractionResult:
        return ExtractionResult()

    async def phrase_question(self, question: Question, context: ExtractionContext) -> str | None:
        return None

    async def generate(
        self, system: str, messages: list[ChatMessage], *, tier: ModelTier, max_tokens: int
    ) -> str:
        self.calls.append((system, messages, tier))
        if self.error is not None:
            raise self.error
        return self.reply

    async def stream(
        self, system: str, messages: list[ChatMessage], *, tier: ModelTier, max_tokens: int
    ) -> AsyncIterator[str]:
        self.calls.append((system, messages, tier))
        if self.error is not None:
            raise self.error
        for index, chunk in enumerate(self.chunks):
            if self.fail_after_chunks is not None and index >= self.fail_after_chunks:
                raise RuntimeError("connection dropped")
            yield chunk
