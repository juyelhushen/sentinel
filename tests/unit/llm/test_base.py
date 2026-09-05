import pytest

from sentinel.llm.base import LLMProvider
from sentinel.llm.models import LLMRequest, LLMResponse, LLMMessage


class FakeLLMProvider(LLMProvider):
    """Fake provider used for testing."""

    def __init__(self, response: str = "Fake response") -> None:
        self._response = response

    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        return LLMResponse(
            content=self._response,
            model="fake-model",
            request_id=request.request_id,
        )

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_llm_provider_generates_response() -> None:
    provider = FakeLLMProvider()

    request = LLMRequest(
        messages=(
            LLMMessage(
                role="user",
                content="Hello Sentinel",
            ),
        ),
    )

    response = await provider.generate(request)

    assert response.content == "Fake response"
    assert response.model == "fake-model"
    assert response.request_id == request.request_id


@pytest.mark.asyncio
async def test_llm_provider_health_check() -> None:
    provider = FakeLLMProvider()

    is_healthy = await provider.health_check()

    assert is_healthy is True