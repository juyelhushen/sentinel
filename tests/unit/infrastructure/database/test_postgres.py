import logging
from unittest.mock import AsyncMock, Mock

import pytest
from psycopg import InterfaceError, OperationalError
from psycopg_pool import PoolTimeout

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


@pytest.mark.parametrize("error_type", [OperationalError, InterfaceError, PoolTimeout])
@pytest.mark.parametrize(
    ("message", "diagnostic"),
    [
        (
            'password authentication failed for user "private-user"',
            "Authentication failed.",
        ),
        ('no pg_hba.conf entry for host "private-host"', "Authentication failed."),
        (
            'could not translate host name "private-host" to address',
            "DNS resolution failed.",
        ),
        (
            "SSL error: certificate verify failed",
            "TLS negotiation or certificate validation failed.",
        ),
        ('database "private-db" does not exist', "Requested database does not exist."),
        ("connection refused", "Network connection failed or timed out."),
        ("connection timed out", "Network connection failed or timed out."),
        ("unknown driver failure", None),
    ],
)
async def test_connection_failure_is_sanitized(
    caplog: pytest.LogCaptureFixture,
    error_type: type[OperationalError | InterfaceError | PoolTimeout],
    message: str,
    diagnostic: str | None,
) -> None:
    url = "postgresql://private-user:p%40ss%2Fword@private-host/private-db"
    secrets = (
        url,
        "private-user:p@ss/word",
        "p@ss/word",
        "p%40ss%2Fword",
        "private-user",
        "private-host",
        "private-db",
        "private-token",
        "/private/client.key",
        "arbitrary-unrecognized-secret",
    )
    details = (
        f"{message}\n{url}\nuser=private-user password='p@ss/word' "
        "host=private-host dbname=private-db token=private-token "
        "sslkey=/private/client.key\narbitrary-unrecognized-secret"
    )
    database = PostgreSQLDatabase(url)
    context = AsyncMock()
    context.__aenter__.side_effect = error_type(details)
    pool = Mock()
    pool.connection.return_value = context
    database._pool = pool
    with (
        caplog.at_level(
            logging.ERROR, logger="sentinel.infrastructure.database.postgres"
        ),
        pytest.raises(DatabaseUnavailable) as error,
    ):
        async with database.connection():
            pytest.fail("failed connection must not yield")
    assert str(error.value) == (
        "Database unavailable. Check connectivity, TLS, and database credentials."
    )
    assert error.value.__suppress_context__
    assert error.value.__cause__ is None
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.ERROR
    assert error_type.__name__ in record.getMessage()
    assert record.exc_info is None
    assert record.stack_info is None
    assert all(secret not in caplog.text for secret in secrets)
    assert all(secret not in repr(record.args) for secret in secrets)
    if diagnostic is None:
        diagnostic = (
            "Timed out waiting for a pooled connection; underlying cause unavailable."
            if error_type is PoolTimeout
            else "Connection failed; unrecognized driver details omitted."
        )
    assert diagnostic in record.getMessage()


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
