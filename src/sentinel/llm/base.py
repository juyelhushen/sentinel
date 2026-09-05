from abc import ABC, abstractmethod

from sentinel.llm.models import LLMRequest, LLMResponse


class LLMProvider(ABC):
    """Abstraction over an LLM providers"""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check the health of the LLM provider."""