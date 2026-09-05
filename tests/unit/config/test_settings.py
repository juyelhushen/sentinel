from sentinel.config.settings import Settings


def test_llm_settings_defaults() -> None:
    settings = Settings()

    assert settings.llm_provider == "ollama"
    assert settings.llm_model == "llama3.2"
    assert settings.llm_base_url == "http://localhost:11434"
    assert settings.llm_timeout_seconds == 60.0
