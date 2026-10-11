from os import environ
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from psycopg import OperationalError
from psycopg.conninfo import conninfo_to_dict

from sentinel.bootstrap.persistence import (
    create_database,
    create_persistence,
    open_persistence,
)
from sentinel.config.settings import get_settings
from sentinel.infrastructure.database.postgres import (
    DatabaseUnavailable,
    PostgreSQLDatabase,
)
from sentinel.infrastructure.database.sqlite import SQLiteDatabase
from sentinel.infrastructure.persistence.postgres.execution_repository import (
    PostgreSQLExecutionRepository,
)
from sentinel.infrastructure.persistence.postgres.incident_repository import (
    PostgreSQLIncidentRepository,
)
from sentinel.infrastructure.persistence.postgres.repair_repository import (
    PostgreSQLRepairRepository,
)
from sentinel.infrastructure.persistence.postgres.tool_execution_repository import (
    PostgreSQLToolExecutionRepository,
)
from sentinel.infrastructure.persistence.sqllite.execution_repository import (
    SQLiteExecutionRepository,
)
from sentinel.infrastructure.persistence.sqllite.incident_repository import (
    SQLiteIncidentRepository,
)
from sentinel.infrastructure.persistence.sqllite.repair_repository import (
    SQLiteRepairRepository,
)
from sentinel.infrastructure.persistence.sqllite.tool_execution_repository import (
    SQLiteToolExecutionRepository,
)
from tests.fixtures.postgres import isolated_local_database, validate_test_target


def _set_postgres_settings(
    monkeypatch,
    *,
    host: str,
    database: str,
    port: str = "5432",
    username: str = "user",
    password: str = "fake",
) -> None:
    for name, value in {
        "DATABASE_BACKEND": "postgresql",
        "DB_HOST": host,
        "DB_PORT": port,
        "DB_NAME": database,
        "DB_USERNAME": username,
        "DB_PASSWORD": password,
        "DB_SSLMODE": "require",
    }.items():
        monkeypatch.setenv(name, value)


def test_repository_selection(tmp_path: Path) -> None:
    sqlite = create_database(f"sqlite:///{tmp_path / 'sentinel.db'}")
    assert isinstance(sqlite, SQLiteDatabase)
    bundle = create_persistence(sqlite)
    assert isinstance(bundle.incidents, SQLiteIncidentRepository)
    assert isinstance(bundle.executions, SQLiteExecutionRepository)
    assert isinstance(bundle.tool_executions, SQLiteToolExecutionRepository)
    assert isinstance(bundle.repairs, SQLiteRepairRepository)

    postgres = create_database("postgresql://user:secret@example.invalid/db")
    assert isinstance(postgres, PostgreSQLDatabase)
    bundle = create_persistence(postgres)
    assert isinstance(bundle.incidents, PostgreSQLIncidentRepository)
    assert isinstance(bundle.executions, PostgreSQLExecutionRepository)
    assert isinstance(bundle.tool_executions, PostgreSQLToolExecutionRepository)
    assert isinstance(bundle.repairs, PostgreSQLRepairRepository)


def test_unsupported_url_is_sanitized() -> None:
    with pytest.raises(DatabaseUnavailable) as error:
        create_database("mysql://user:secret@example.invalid/db")
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("fail", [True, False])
async def test_postgres_lifespan_always_closes_pool(fail: bool) -> None:
    database = PostgreSQLDatabase("postgresql://example.invalid/db")
    database.open = AsyncMock()
    database.close = AsyncMock()
    initializer = AsyncMock(side_effect=OperationalError("secret") if fail else None)
    with (
        patch("sentinel.bootstrap.persistence.create_database", return_value=database),
        patch("sentinel.bootstrap.persistence.initialize_postgres_schema", initializer),
    ):
        if fail:
            with pytest.raises(DatabaseUnavailable) as error:
                async with open_persistence("postgresql://example.invalid/db"):
                    pytest.fail("failed initialization must not yield")
            assert "secret" not in str(error.value)
        else:
            async with open_persistence("postgresql://example.invalid/db") as bundle:
                assert isinstance(bundle.incidents, PostgreSQLIncidentRepository)
    database.open.assert_awaited_once()
    database.close.assert_awaited_once()


@pytest.mark.parametrize(
    "application_url,test_url",
    [
        (
            "postgresql://user:fake@localhost:5432/sentinel",
            "postgres://user:fake@127.0.0.1/sentinel",
        ),
        (
            "postgresql://user:fake@db.example.invalid:5432/sentinel",
            "postgresql://user:fake@db.example.invalid:6543/sentinel",
        ),
    ],
)
def test_postgres_integration_guard_rejects_application_target(
    monkeypatch,
    application_url: str,
    test_url: str,
) -> None:
    parameters = conninfo_to_dict(application_url)
    _set_postgres_settings(
        monkeypatch,
        host=parameters["host"],
        port=parameters["port"],
        database=parameters["dbname"],
        username=parameters["user"],
        password=parameters["password"],
    )
    with pytest.raises(pytest.fail.Exception, match="separate test database"):
        validate_test_target(test_url)


def test_postgres_integration_guard_reads_dotenv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/sentinel.db")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "DATABASE_BACKEND=postgresql\n"
        "DB_HOST=db.example.invalid\n"
        "DB_NAME=sentinel\n"
        "DB_USERNAME=user\n"
        "DB_PASSWORD=fake\n",
        encoding="utf-8",
    )
    with pytest.raises(pytest.fail.Exception, match="separate test database"):
        validate_test_target("postgresql://user:fake@db.example.invalid/sentinel")


def test_postgres_integration_guard_accepts_dedicated_database(monkeypatch) -> None:
    _set_postgres_settings(monkeypatch, host="localhost", database="sentinel")
    validate_test_target("postgresql://user:fake@localhost/sentinel_test")


@pytest.mark.parametrize(
    "test_url", ["postgresql://user:fake@[invalid/db", "postgresql:///db"]
)
def test_postgres_integration_guard_rejects_ambiguous_or_invalid_target(
    monkeypatch,
    test_url: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/sentinel.db")
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    with pytest.raises(pytest.fail.Exception) as error:
        validate_test_target(test_url)
    assert "fake" not in str(error.value)


def test_local_runner_refuses_remote_endpoint_before_connecting(monkeypatch) -> None:
    _set_postgres_settings(monkeypatch, host="remote.invalid", database="test")
    with patch("tests.fixtures.postgres.psycopg.connect") as connect:
        with pytest.raises(RuntimeError, match="loopback"), isolated_local_database():
            pytest.fail("remote target must not yield")
        connect.assert_not_called()


@pytest.mark.parametrize("fail", [False, True])
def test_local_runner_restores_environment_and_drops_only_test_database(
    monkeypatch,
    fail: bool,
) -> None:
    application_url = "postgresql://user:fake@localhost:5432/sentinel?sslmode=require"
    original_test_url = "postgresql://localhost/existing_test"
    _set_postgres_settings(monkeypatch, host="localhost", database="sentinel")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/sentinel.db")
    monkeypatch.setenv("TEST_POSTGRES_URL", original_test_url)
    admin = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = admin

    def check() -> None:
        with isolated_local_database():
            parameters = conninfo_to_dict(environ["TEST_POSTGRES_URL"])
            assert parameters["dbname"].startswith("sentinel_verify_")
            assert get_settings().database_connection_url == application_url
            if fail:
                raise RuntimeError("test failure")

    with patch("tests.fixtures.postgres.psycopg.connect", return_value=context):
        if fail:
            with pytest.raises(RuntimeError, match="test failure"):
                check()
        else:
            check()

    assert environ["DATABASE_URL"] == "sqlite:///./data/sentinel.db"
    assert environ["TEST_POSTGRES_URL"] == original_test_url
    assert admin.execute.call_count == 2
    create, drop = [call.args[0].as_string() for call in admin.execute.call_args_list]
    assert create.startswith('CREATE DATABASE "sentinel_verify_')
    assert drop == create.replace("CREATE DATABASE", "DROP DATABASE", 1)
