from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    app_name: str = "sentinel"
    environment: str = "development"
    log_level: str = "INFO"

    database_backend: Literal["sqlite", "postgresql"] = "sqlite"
    database_url: str = Field(default="sqlite:///./data/sentinel.db", repr=False)
    db_host: str | None = None
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str | None = None
    db_username: str | None = Field(default=None, repr=False)
    db_password: SecretStr | None = Field(default=None, repr=False)
    db_sslmode: Literal[
        "disable", "allow", "prefer", "require", "verify-ca", "verify-full"
    ] = "require"
    database_schema: str = "sentinel"
    database_connect_timeout_seconds: int = Field(default=10, ge=1, le=300)
    database_pool_size: int = Field(default=5, ge=1, le=50)

    llm_provider: str = "ollama"
    llm_model: str = Field(
        default="llama3.2",
        validation_alias=AliasChoices("OLLAMA_MODEL", "LLM_MODEL"),
    )
    llm_base_url: str = Field(
        default="http://localhost:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "LLM_BASE_URL"),
    )
    llm_temperature: float = 0.0
    llm_timeout_seconds: float = 60.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_key: SecretStr | None = Field(
        default=None,
        validation_alias="SENTINEL_API_KEY",
    )

    repository_root: Path = Field(
        default=Path("./workspace"),
        validation_alias="SENTINEL_REPOSITORY_ROOT",
    )

    @property
    def database_connection_url(self) -> str:
        """Return the selected backend URL without storing it in Settings repr."""
        if self.database_backend == "sqlite":
            return self.database_url

        missing = [
            name
            for name, value in (
                ("DB_HOST", self.db_host),
                ("DB_NAME", self.db_name),
                ("DB_USERNAME", self.db_username),
                (
                    "DB_PASSWORD",
                    self.db_password.get_secret_value()
                    if self.db_password is not None
                    else None,
                ),
            )
            if value is None or not value.strip()
        ]
        if missing:
            raise ValueError(
                "PostgreSQL backend requires non-empty settings: " + ", ".join(missing)
            )
        assert self.db_host is not None
        assert self.db_name is not None
        assert self.db_username is not None
        assert self.db_password is not None

        host = self.db_host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        password = self.db_password.get_secret_value()
        return (
            f"postgresql://{quote(self.db_username, safe='')}:{quote(password, safe='')}"
            f"@{host}:{self.db_port}/{quote(self.db_name, safe='')}"
            f"?sslmode={self.db_sslmode}"
        )


def get_settings() -> Settings:
    """Return application settings."""
    return Settings()
