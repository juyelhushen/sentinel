import pytest

from sentinel.llm.models import LLMMessage, LLMRequest
from sentinel.llm.ollama import OllamaProvider


@pytest.mark.asyncio
async def test_ollama_provider_generates_response() -> None:
    provider = OllamaProvider(
        model="llama3.2",
        base_url="http://localhost:11434",
    )

    request = LLMRequest(
        messages=(
            LLMMessage(
                role="user",
                content="Reply with exactly: Sentinel works",
            ),
        ),
    )

    response = await provider.generate(request)

    assert response.content
    assert response.model == "llama3.2"
