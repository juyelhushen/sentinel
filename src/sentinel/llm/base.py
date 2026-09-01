from abc import ABC

from sentinel.llm.models import LLMRequest, LLMResponse


class LLMProvider(ABC):
    """Abstraction over an LLM providers"""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM."""
