import asyncio

from ollama import AsyncClient

from sentinel.llm.base import LLMProvider
from sentinel.llm.exceptions import LLMConnectionError
from sentinel.llm.models import LLMRequest, LLMResponse


class OllamaProvider(LLMProvider):
    """Ollama implementation of the LLM provider."""

    def __init__(
        self,
        model: str,
        base_url: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._client = AsyncClient(host=base_url)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            response = await asyncio.wait_for(
                self._client.chat(
                    model=self._model,
                    messages=[
                        {
                            "role": message.role,
                            "content": message.content,
                        }
                        for message in request.messages
                    ],
                    options={
                        "temperature": request.temperature,
                    },
                ),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise LLMConnectionError("Ollama request timed out.") from exc
        except Exception as exc:
            raise LLMConnectionError("Failed to connect to Ollama.") from exc

        try:
            content = response["message"]["content"]
        except KeyError, TypeError:
            raise LLMConnectionError("Ollama returned an invalid response.")

        return LLMResponse(
            content=content,
            model=self._model,
            request_id=request.request_id,
            input_tokens=response.get("prompt_eval_count"),
            output_tokens=response.get("eval_count"),
            finish_reason=None,
        )
