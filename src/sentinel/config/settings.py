from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    app_name: str = "sentinel"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./data/sentinel.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


def get_settings() -> Settings:
    """Returns Cache Application Settings."""
    return Settings()
