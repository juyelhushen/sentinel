import pytest

from sentinel.config.settings import get_settings
from sentinel.llm.models import LLMMessage, LLMRequest
from sentinel.llm.ollama import OllamaProvider


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ollama_provider_generates_response() -> None:
    settings = get_settings()

    provider = OllamaProvider(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )

    request = LLMRequest(
        messages=(
            LLMMessage(
                role="user",
                content="Reply with exactly: Sentinel works",
            ),
        ),
        temperature=0.0,
    )

    response = await provider.generate(request)

    assert response.content
    assert response.model == settings.llm_model
    assert response.request_id == request.request_id
