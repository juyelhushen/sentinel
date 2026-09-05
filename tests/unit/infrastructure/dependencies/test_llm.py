from sentinel.infrastructure.dependencies.llm import create_llm_provider
from sentinel.llm.ollama import OllamaProvider


def test_create_llm_provider_returns_ollama_provider() -> None:
    provider = create_llm_provider()

    assert isinstance(provider, OllamaProvider)