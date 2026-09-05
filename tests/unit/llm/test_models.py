from sentinel.llm.models import LLMRequest, LLMMessage, LLMResponse


def test_llm_request_generates_request_id() -> None:
    request = LLMRequest(
        messages=(
            LLMMessage(
                role="user",
                content="Hello",
            ),
        ),
    )

    assert request.request_id is not None


def test_llm_response_preserves_request_id() -> None:
    request = LLMRequest(
        messages=(
            LLMMessage(
                role="user",
                content="Hello",
            ),
        ),
    )

    response = LLMResponse(
        content="Hello",
        model="test-model",
        request_id=request.request_id,
    )

    assert response.request_id == request.request_id
    assert response.content == "Hello"
    assert response.model == "test-model"