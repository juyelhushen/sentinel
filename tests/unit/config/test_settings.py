import pytest
from pydantic import ValidationError

from sentinel.config.settings import Settings


def test_llm_settings_defaults() -> None:
    settings = Settings()

    assert settings.llm_provider == "ollama"
    assert settings.llm_model == "llama3.2"
    assert settings.llm_base_url == "http://localhost:11434"
    assert settings.llm_timeout_seconds == 60.0


def test_database_environment_configuration(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./custom/sentinel.db")
    monkeypatch.setenv("DATABASE_SCHEMA", "sentinel_custom")
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("DATABASE_POOL_SIZE", "3")
    settings = Settings(_env_file=None)
    assert settings.database_url == "sqlite:///./custom/sentinel.db"
    assert settings.database_schema == "sentinel_custom"
    assert settings.database_connect_timeout_seconds == 12
    assert settings.database_pool_size == 3
    assert "secret" not in repr(settings)


def test_sqlite_backend_is_default_and_ignores_incomplete_postgres_settings() -> None:
    settings = Settings(_env_file=None, DB_HOST="partial-host")
    assert settings.database_backend == "sqlite"
    assert settings.database_connection_url == "sqlite:///./data/sentinel.db"


def test_postgres_backend_builds_url_from_separate_environment_variables(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATABASE_BACKEND", "postgresql")
    monkeypatch.setenv(
        "DB_HOST", "ep-lively-unit-a1pvq2yh-pooler.ap-southeast-1.aws.neon.tech"
    )
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "sentinel_db")
    monkeypatch.setenv("DB_USERNAME", "neondb_owner")
    monkeypatch.setenv("DB_PASSWORD", "p@ss:/?#%word")
    monkeypatch.setenv("DB_SSLMODE", "require")

    settings = Settings(_env_file=None)

    assert settings.database_backend == "postgresql"
    assert settings.database_connection_url == (
        "postgresql://neondb_owner:p%40ss%3A%2F%3F%23%25word@"
        "ep-lively-unit-a1pvq2yh-pooler.ap-southeast-1.aws.neon.tech:5432/"
        "sentinel_db?sslmode=require"
    )
    assert "p@ss" not in repr(settings)
    assert "sentinel_db" in settings.database_connection_url


@pytest.mark.parametrize(
    "missing_environment",
    [
        "DB_HOST",
        "DB_NAME",
        "DB_USERNAME",
        "DB_PASSWORD",
    ],
)
def test_postgres_backend_requires_connection_fields(
    monkeypatch, missing_environment: str
) -> None:
    values = {
        "DATABASE_BACKEND": "postgresql",
        "DB_HOST": "localhost",
        "DB_NAME": "neondb",
        "DB_USERNAME": "neondb_owner",
        "DB_PASSWORD": "local-test-secret",
    }
    values.pop(missing_environment)
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(missing_environment, raising=False)

    settings = Settings(_env_file=None)
    with pytest.raises(ValueError) as error:
        assert settings.database_connection_url

    assert missing_environment in str(error.value)
    assert "local-test-secret" not in str(error.value)


def test_unsupported_backend_rejected_without_echoing_password(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_BACKEND", "mysql")
    monkeypatch.setenv("DB_PASSWORD", "local-test-secret")
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)
    assert "local-test-secret" not in str(error.value)
