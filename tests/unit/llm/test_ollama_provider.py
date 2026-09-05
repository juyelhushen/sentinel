import pytest

from sentinel.config.settings import get_settings
from sentinel.llm.exceptions import LLMConnectionError
from sentinel.llm.models import LLMRequest, LLMMessage
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