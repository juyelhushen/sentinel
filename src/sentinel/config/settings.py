from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    app_name: str = "sentinel"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./data/sentinel.db"

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
    
    repository_root: Path = Field(
        default=Path("./workspace"),
        validation_alias="SENTINEL_REPOSITORY_ROOT",
    )


def get_settings() -> Settings:
    """Return application settings."""
    return Settings()