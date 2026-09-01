import pytest

from sentinel.llm.base import LLMProvider
from sentinel.llm.models import LLMMessage, LLMRequest, LLMResponse


class FakeLLMProvider(LLMProvider):
    def __init__(self, response: str) -> None:
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

    @pytest.mark.asyncio
    async def test_fake_llm_returns_response(self) -> None:
        provider = FakeLLMProvider(response="Hello Sentinel")
        request = LLMRequest(
            messages=(
                LLMMessage(
                    role="user",
                    content="Hello",
                ),
            )
        )

        response = await provider.generate(request)

        assert response.content == "Hello Sentinel"
        assert response.model == "fake-model"
        assert response.request_id == request.request_id
