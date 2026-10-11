from unittest.mock import AsyncMock, Mock

import pytest
from psycopg import OperationalError

from sentinel.infrastructure.database.postgres import (
    DatabaseUnavailable,
    PostgreSQLDatabase,
)


@pytest.mark.parametrize("scheme", ["postgresql", "postgres"])
def test_postgres_pool_configuration_preserves_secure_url(scheme: str) -> None:
    url = f"{scheme}://user:password@example.invalid:6543/test?sslmode=verify-full"
    database = PostgreSQLDatabase(url, timeout_seconds=7, pool_size=3)
    assert database._pool.conninfo == url
    assert database._pool.kwargs["sslmode"] == "verify-full"
    assert database._pool.kwargs["prepare_threshold"] is None
    assert database._pool.kwargs["connect_timeout"] == 7
    assert database._pool.max_size == 3


@pytest.mark.parametrize("sslmode", ["disable", "allow", "prefer"])
def test_remote_postgres_rejects_insecure_tls(sslmode: str) -> None:
    with pytest.raises(DatabaseUnavailable, match="require TLS"):
        PostgreSQLDatabase(
            f"postgresql://user:secret@example.invalid/db?sslmode={sslmode}"
        )


def test_default_tls_and_local_explicit_opt_out() -> None:
    database = PostgreSQLDatabase("postgresql://user:secret@example.invalid/db")
    assert database._pool.kwargs["sslmode"] == "require"
    local = PostgreSQLDatabase("postgresql://localhost/test?sslmode=disable")
    assert local._pool.kwargs["sslmode"] == "disable"


def test_invalid_configuration_does_not_expose_credentials() -> None:
    with pytest.raises(DatabaseUnavailable) as error:
        PostgreSQLDatabase(
            "postgresql://user:secret@example.invalid/db", schema="bad;sql"
        )
    assert "secret" not in str(error.value)

    with pytest.raises(DatabaseUnavailable) as malformed:
        PostgreSQLDatabase("postgresql://user:secret@[invalid/db")
    assert "secret" not in str(malformed.value)
    assert malformed.value.__suppress_context__


async def test_connection_failure_is_sanitized() -> None:
    database = PostgreSQLDatabase("postgresql://user:secret@example.invalid/db")
    context = AsyncMock()
    context.__aenter__.side_effect = OperationalError("secret connection details")
    pool = Mock()
    pool.connection.return_value = context
    database._pool = pool
    with pytest.raises(DatabaseUnavailable) as error:
        async with database.connection():
            pytest.fail("failed connection must not yield")
    assert "secret" not in str(error.value)
    assert error.value.__suppress_context__


async def test_pool_lifecycle_and_transaction_scoped_schema() -> None:
    database = PostgreSQLDatabase("postgresql://example.invalid/db")
    connection = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = connection
    pool = Mock(open=AsyncMock(), close=AsyncMock())
    pool.connection.return_value = context
    database._pool = pool
    await database.open()
    async with database.connection() as acquired:
        assert acquired is connection
    await database.close()
    pool.open.assert_awaited_once()
    pool.close.assert_awaited_once()
    connection.execute.assert_awaited_once_with(
        "SELECT set_config('search_path', %s, true)", ('"sentinel", pg_catalog',)
    )
    context.__aexit__.assert_awaited_once()
