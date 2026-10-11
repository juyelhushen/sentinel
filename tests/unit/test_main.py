from pathlib import Path
from unittest.mock import AsyncMock, Mock

from sentinel.config.settings import Settings
from sentinel.infrastructure.database.sqlite import SQLiteDatabase
from sentinel.main import main


def test_main_runs(monkeypatch, tmp_path: Path, capsys) -> None:
    database_path = tmp_path / "sentinel.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    main()
    assert capsys.readouterr().out.startswith("Created incident: ")
    with SQLiteDatabase(database_path).transaction() as connection:
        assert connection.execute("SELECT title FROM incidents").fetchall() == [
            ("Example incident",)
        ]


def test_main_uses_configured_postgres_persistence(monkeypatch, capsys) -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_BACKEND="postgresql",
        DB_HOST="localhost",
        DB_NAME="test",
        DB_USERNAME="postgres",
        DB_PASSWORD="unit-test-password",
        DB_SSLMODE="require",
    )
    repository = Mock(persist=AsyncMock())
    context = AsyncMock()
    context.__aenter__.return_value = Mock(incidents=repository)
    factory = Mock(return_value=context)
    monkeypatch.setattr("sentinel.main.get_settings", lambda: settings)
    monkeypatch.setattr("sentinel.main.open_persistence", factory)

    main()

    factory.assert_called_once_with(
        settings.database_connection_url,
        schema=settings.database_schema,
        timeout_seconds=settings.database_connect_timeout_seconds,
        pool_size=settings.database_pool_size,
    )
    repository.persist.assert_awaited_once()
    context.__aexit__.assert_awaited_once()
    assert capsys.readouterr().out.startswith("Created incident: ")
