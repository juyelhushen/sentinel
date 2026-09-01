from sentinel.config.settings import get_settings
from sentinel.llm.base import LLMProvider
from sentinel.llm.ollama import OllamaProvider


def create_llm_provider() -> LLMProvider:
    """Create the configured LLM provider."""

    settings = get_settings()

    if settings.llm_provider == "ollama":
        return OllamaProvider(
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
