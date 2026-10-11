from sentinel.config.settings import Settings


def test_llm_settings_defaults() -> None:
    settings = Settings()

    assert settings.llm_provider == "ollama"
    assert settings.llm_model == "llama3.2"
    assert settings.llm_base_url == "http://localhost:11434"
    assert settings.llm_timeout_seconds == 60.0


def test_database_environment_configuration(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@example.invalid/test")
    monkeypatch.setenv("DATABASE_SCHEMA", "sentinel_custom")
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("DATABASE_POOL_SIZE", "3")
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("postgresql://")
    assert settings.database_schema == "sentinel_custom"
    assert settings.database_connect_timeout_seconds == 12
    assert settings.database_pool_size == 3
    assert "secret" not in repr(settings)
