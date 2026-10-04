"""Claude through the Anthropic API (official ``anthropic`` SDK).

Only moves text: prompts, validation and grounding live in ``app.services.compass_ai``.
The old Planner session API keeps the stub's rule-based extraction (inherited), since the
current front end doesn't use it.

* Model: Claude Sonnet by default (``AI_MODEL_FAST`` / ``AI_MODEL_SMART``).
* Thinking: adaptive (the model default) at ``AI_EFFORT`` (default ``low``). Thinking
  tokens count toward ``max_tokens``, so callers size it with headroom.
* Refusals: ``stop_reason == "refusal"`` is a failure, never text. Server-side fallbacks
  (``fallbacks: "default"``) are on unless ``AI_REFUSAL_FALLBACKS=false``.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from app.ai.base import ChatMessage, ModelFailed, ModelThrottled, ModelTier, ModelUnavailable
from app.ai.stub import StubAIAdapter
from app.settings import Settings

logger = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


def map_error(exc: Exception) -> Exception:
    """Translate SDK errors into the adapter's three outcomes.

    Unavailable (503 to the front end, which then uses its fallbacks for the session):
    bad key, missing permission, unknown model - configuration problems a retry won't fix.
    Throttled (429): rate limits and overload. Failed: everything else, including
    timeouts and network errors, which are worth retrying on the next message.
    """
    if isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        return ModelUnavailable("authentication")
    if isinstance(exc, anthropic.NotFoundError):
        return ModelUnavailable("model not found")
    if isinstance(exc, anthropic.RateLimitError | anthropic.OverloadedError):
        return ModelThrottled()
    return ModelFailed(type(exc).__name__)


class ClaudeAdapter(StubAIAdapter):
    def __init__(self, settings: Settings, client: Any = None) -> None:
        if client is None:
            if settings.anthropic_api_key is None:
                raise ValueError("ANTHROPIC_API_KEY is required for the anthropic provider")
            client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key.get_secret_value().strip(),
                # The service enforces its own deadline (AI_TIMEOUT_SECONDS); one quick
                # SDK retry covers transient 429/5xx/network blips.
                max_retries=1,
                timeout=60.0,
            )
        self._client = client
        self._models: dict[ModelTier, str] = {
            "fast": settings.ai_model_fast,
            "smart": settings.ai_model_smart,
        }
        self._effort = settings.ai_effort
        self._fallbacks = settings.ai_refusal_fallbacks
        self.model_id = settings.ai_model_smart

    def _params(
        self, system: str, messages: list[ChatMessage], tier: ModelTier, max_tokens: int
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self._models[tier],
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "output_config": {"effort": self._effort},
        }
        if self._fallbacks:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        return params

    async def generate(
        self, system: str, messages: list[ChatMessage], *, tier: ModelTier, max_tokens: int
    ) -> str:
        try:
            response = await self._client.beta.messages.create(
                **self._params(system, messages, tier, max_tokens)
            )
        except anthropic.APIError as exc:
            raise self._log_and_map(exc) from exc
        if response.stop_reason == "refusal":
            logger.warning("claude_refusal", extra={"ai_model_id": self._models[tier]})
            raise ModelFailed("refusal")
        # Read text blocks by type: with thinking on, the reply can start with a
        # (possibly empty) thinking block.
        text = "".join(block.text for block in response.content if block.type == "text")
        if not text.strip():
            raise ModelFailed("empty reply")
        return text

    async def stream(
        self, system: str, messages: list[ChatMessage], *, tier: ModelTier, max_tokens: int
    ) -> AsyncIterator[str]:
        try:
            async with self._client.beta.messages.stream(
                **self._params(system, messages, tier, max_tokens)
            ) as stream:
                async for text in stream.text_stream:
                    if text:
                        yield text
                final = await stream.get_final_message()
        except anthropic.APIError as exc:
            raise self._log_and_map(exc) from exc
        if final.stop_reason == "refusal":
            # Before any text this becomes a 502; mid-answer the stream just ends.
            logger.warning("claude_refusal", extra={"ai_model_id": self._models[tier]})
            raise ModelFailed("refusal")

    def _log_and_map(self, exc: Exception) -> Exception:
        mapped = map_error(exc)
        level = logging.ERROR if isinstance(mapped, ModelUnavailable) else logging.WARNING
        logger.log(
            level,
            "claude_error",
            extra={"ai_model_id": self.model_id, "error_code": type(exc).__name__},
        )
        return mapped
