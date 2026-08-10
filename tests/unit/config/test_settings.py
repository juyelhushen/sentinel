from sentinel.config.settings import Settings


def test_default_settings() -> None:
    settings = Settings()

    assert settings.app_name == "sentinel"
    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.database_url == "sqlite:///./data/sentinel.db"
