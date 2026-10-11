from unittest.mock import AsyncMock

import pytest
from httpx import ConnectTimeout, ReadError, ReadTimeout
from ollama import ResponseError

from sentinel.config.settings import get_settings
from sentinel.llm.exceptions import LLMConnectionError
from sentinel.llm.models import LLMMessage, LLMRequest
from sentinel.llm.ollama import OllamaProvider


@pytest.mark.asyncio
async def test_ollama_provider_maps_connection_errors() -> None:
    provider = OllamaProvider(
        model="llama3.2",
        base_url="http://localhost:65535",
    )

    request = LLMRequest(
        messages=(
            LLMMessage(
                role="user",
                content="Hello",
            ),
        ),
    )

    with pytest.raises(LLMConnectionError):
        await provider.generate(request)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("request timed out"),
        ConnectionError("connection refused"),
        ConnectTimeout("connection timed out"),
        ReadTimeout("read timed out"),
        ReadError("connection lost"),
        ResponseError("unauthorized", status_code=401),
    ],
)
async def test_health_check_returns_false_for_expected_errors(
    error: Exception,
) -> None:
    provider = OllamaProvider(model="llama3.2", base_url="http://localhost:11434")
    provider._client.list = AsyncMock(side_effect=error)

    assert await provider.health_check() is False


@pytest.mark.asyncio
async def test_health_check_returns_true_when_available() -> None:
    provider = OllamaProvider(model="llama3.2", base_url="http://localhost:11434")
    provider._client.list = AsyncMock(return_value={})

    assert await provider.health_check() is True


@pytest.mark.asyncio
async def test_ollama_propagates_unexpected_errors() -> None:
    provider = OllamaProvider(model="llama3.2", base_url="http://localhost:11434")
    provider._client.list = AsyncMock(side_effect=TypeError("invalid client"))
    provider._client.chat = AsyncMock(side_effect=TypeError("invalid client"))

    with pytest.raises(TypeError, match="invalid client"):
        await provider.health_check()

    with pytest.raises(TypeError, match="invalid client"):
        await provider.generate(
            LLMRequest(messages=(LLMMessage(role="user", content="Hello"),))
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ollama_provider_health_check() -> None:
    settings = get_settings()

    provider = OllamaProvider(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )

    is_healthy = await provider.health_check()

    assert is_healthy is True
