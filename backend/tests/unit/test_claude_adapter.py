"""ClaudeAdapter against a fake Anthropic client: request shape, replies, refusals, errors."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from app.ai.base import ChatMessage, ModelFailed, ModelThrottled, ModelUnavailable
from app.ai.claude import FALLBACK_BETA, ClaudeAdapter, map_error
from app.settings import Settings

KEY = "sk-ant-test-not-a-real-key"


def settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, ai_provider="anthropic", anthropic_api_key=KEY, **overrides)


def message(*blocks: Any, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


def text(value: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=value)


def thinking() -> SimpleNamespace:
    return SimpleNamespace(type="thinking", thinking="")


class FakeStream:
    def __init__(self, chunks: list[str], final: SimpleNamespace) -> None:
        self._chunks = chunks
        self._final = final

    async def __aenter__(self) -> FakeStream:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    @property
    def text_stream(self) -> AsyncIterator[str]:
        async def gen() -> AsyncIterator[str]:
            for chunk in self._chunks:
                yield chunk

        return gen()

    async def get_final_message(self) -> SimpleNamespace:
        return self._final


class FakeMessages:
    def __init__(
        self, reply: Any = None, chunks: list[str] | None = None, error: Exception | None = None
    ) -> None:
        self.reply = reply
        self.chunks = chunks or []
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def create(self, **params: Any) -> Any:
        self.calls.append(params)
        if self.error:
            raise self.error
        return self.reply

    def stream(self, **params: Any) -> FakeStream:
        self.calls.append(params)
        if self.error:
            raise self.error
        return FakeStream(self.chunks, self.reply or message(text("".join(self.chunks))))


def adapter(fake: FakeMessages, **overrides: Any) -> ClaudeAdapter:
    client = SimpleNamespace(beta=SimpleNamespace(messages=fake))
    return ClaudeAdapter(settings(**overrides), client=client)


USER = [ChatMessage("user", "Term or whole life?")]


def test_settings_require_a_key_for_the_anthropic_provider() -> None:
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        Settings(_env_file=None, ai_provider="anthropic")
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        Settings(_env_file=None, ai_provider="anthropic", anthropic_api_key="  ")


def test_api_key_never_appears_in_settings_output() -> None:
    s = settings()
    assert KEY not in repr(s)
    assert KEY not in str(s.model_dump())


def test_request_shape_defaults_to_sonnet_low_effort_with_fallbacks() -> None:
    fake = FakeMessages(reply=message(text('{"updates": {}}')))
    asyncio.run(adapter(fake).generate("SYSTEM", USER, tier="fast", max_tokens=4000))
    [params] = fake.calls
    assert params["model"] == "claude-sonnet-5-5"
    assert params["max_tokens"] == 4000
    assert params["system"] == "SYSTEM"
    assert params["messages"] == [{"role": "user", "content": "Term or whole life?"}]
    assert params["output_config"] == {"effort": "low"}
    assert params["betas"] == [FALLBACK_BETA]
    assert params["fallbacks"] == "default"
    # Sonnet 5.5 rejects disabled thinking and non-default sampling: send neither.
    assert "thinking" not in params
    assert "temperature" not in params


def test_models_effort_and_fallbacks_are_configurable() -> None:
    fake = FakeMessages(reply=message(text("ok")))
    a = adapter(
        fake,
        ai_model_fast="claude-haiku-4-5",
        ai_effort="medium",
        ai_refusal_fallbacks=False,
    )
    asyncio.run(a.generate("S", USER, tier="fast", max_tokens=100))
    asyncio.run(a.generate("S", USER, tier="smart", max_tokens=100))
    assert [c["model"] for c in fake.calls] == ["claude-haiku-4-5", "claude-sonnet-5-5"]
    assert fake.calls[0]["output_config"] == {"effort": "medium"}
    assert "fallbacks" not in fake.calls[0] and "betas" not in fake.calls[0]


def test_generate_reads_text_blocks_by_type() -> None:
    fake = FakeMessages(reply=message(thinking(), text("Hello "), text("there")))
    assert (
        asyncio.run(adapter(fake).generate("S", USER, tier="smart", max_tokens=100))
        == "Hello there"
    )


def test_generate_refusal_is_a_failure_not_text() -> None:
    fake = FakeMessages(reply=message(text(""), stop_reason="refusal"))
    with pytest.raises(ModelFailed, match="refusal"):
        asyncio.run(adapter(fake).generate("S", USER, tier="fast", max_tokens=100))


def test_generate_empty_reply_is_a_failure() -> None:
    fake = FakeMessages(reply=message(thinking()))
    with pytest.raises(ModelFailed):
        asyncio.run(adapter(fake).generate("S", USER, tier="fast", max_tokens=100))


def collect(a: ClaudeAdapter) -> list[str]:
    async def run() -> list[str]:
        return [c async for c in a.stream("S", USER, tier="smart", max_tokens=8000)]

    return asyncio.run(run())


def test_stream_yields_text_chunks() -> None:
    fake = FakeMessages(chunks=["Term ", "", "fits."])
    assert collect(adapter(fake)) == ["Term ", "fits."]
    assert fake.calls[0]["model"] == "claude-sonnet-5-5"


def test_stream_refusal_raises_after_any_text() -> None:
    fake = FakeMessages(chunks=[], reply=message(stop_reason="refusal"))
    with pytest.raises(ModelFailed, match="refusal"):
        collect(adapter(fake))


REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def status_error(cls: type[anthropic.APIStatusError], code: int) -> anthropic.APIStatusError:
    return cls("error", response=httpx2.Response(code, request=REQUEST), body=None)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (status_error(anthropic.AuthenticationError, 401), ModelUnavailable),
        (status_error(anthropic.PermissionDeniedError, 403), ModelUnavailable),
        (status_error(anthropic.NotFoundError, 404), ModelUnavailable),
        (status_error(anthropic.RateLimitError, 429), ModelThrottled),
        (status_error(anthropic.OverloadedError, 529), ModelThrottled),
        (status_error(anthropic.BadRequestError, 400), ModelFailed),
        (status_error(anthropic.InternalServerError, 500), ModelFailed),
        (anthropic.APITimeoutError(request=REQUEST), ModelFailed),
        (anthropic.APIConnectionError(request=REQUEST), ModelFailed),
    ],
)
def test_error_mapping(error: Exception, expected: type[Exception]) -> None:
    assert isinstance(map_error(error), expected)
    fake = FakeMessages(error=error)
    with pytest.raises(expected):
        asyncio.run(adapter(fake).generate("S", USER, tier="fast", max_tokens=100))
    with pytest.raises(expected):
        collect(adapter(FakeMessages(error=error)))


def test_container_selects_claude_when_configured() -> None:
    from app.container import build_ai_adapter

    assert isinstance(build_ai_adapter(settings()), ClaudeAdapter)
