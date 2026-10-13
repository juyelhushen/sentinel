import hashlib
import logging
from unittest.mock import AsyncMock, Mock

import pytest
from psycopg import OperationalError

from sentinel.infrastructure.database.postgres import (
    DatabaseUnavailable,
    PostgreSQLDatabase,
)
from sentinel.infrastructure.persistence.postgres.rate_limiter import (
    PostgreSQLRateLimitStore,
)


def _store_with_connection(
    *, request_count: int = 0, retry_after: int = 1
) -> tuple[PostgreSQLRateLimitStore, AsyncMock, AsyncMock]:
    database = PostgreSQLDatabase("postgresql://example.invalid/db")
    cursor = AsyncMock()
    cursor.fetchone.return_value = {
        "request_count": request_count,
        "retry_after": retry_after,
    }
    connection = AsyncMock()
    connection.execute.side_effect = [None, None, cursor, None]
    context = AsyncMock()
    context.__aenter__.return_value = connection
    database.connection = Mock(return_value=context)
    return PostgreSQLRateLimitStore(database), connection, cursor


async def test_rate_limit_store_hashes_key_and_cleans_expired_records() -> None:
    store, connection, _ = _store_with_connection()
    raw_key = "raw-private-api-key"

    assert await store.check_and_record(raw_key, "POST:/incidents", 10) is None

    calls = connection.execute.await_args_list
    assert "DELETE FROM rate_limit_requests" in calls[0].args[0]
    assert "expires_at <= clock_timestamp()" in calls[0].args[0]
    assert "pg_advisory_xact_lock" in calls[1].args[0]
    assert raw_key not in repr(calls)
    assert calls[2].args[1] == (
        60,
        hashlib.sha256(raw_key.encode()).digest(),
        "POST:/incidents",
        60,
    )
    assert "INSERT INTO rate_limit_requests" in calls[3].args[0]
    assert calls[3].args[1] == (
        hashlib.sha256(raw_key.encode()).digest(),
        "POST:/incidents",
        60,
    )


async def test_rate_limit_store_returns_retry_after_without_insert() -> None:
    store, connection, _ = _store_with_connection(request_count=2, retry_after=23)

    assert await store.check_and_record("key", "GET:/health", 2) == 23
    assert connection.execute.await_count == 3


async def test_database_failure_fails_closed_without_logging_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    database = PostgreSQLDatabase("postgresql://private-user:private-password@host/db")
    context = AsyncMock()
    context.__aenter__.side_effect = OperationalError(
        "password private-password; api key raw-private-api-key"
    )
    database.connection = Mock(return_value=context)
    store = PostgreSQLRateLimitStore(database)

    with caplog.at_level(logging.ERROR), pytest.raises(DatabaseUnavailable) as error:
        await store.check_and_record("raw-private-api-key", "POST:/incidents", 10)

    assert str(error.value) == "Rate limiting is temporarily unavailable."
    assert error.value.__suppress_context__
    assert "OperationalError" in caplog.text
    assert "private-password" not in caplog.text
    assert "raw-private-api-key" not in caplog.text


async def test_database_unavailable_is_preserved() -> None:
    database = PostgreSQLDatabase("postgresql://example.invalid/db")
    context = AsyncMock()
    context.__aenter__.side_effect = DatabaseUnavailable("Database unavailable.")
    database.connection = Mock(return_value=context)
    store = PostgreSQLRateLimitStore(database)

    with pytest.raises(DatabaseUnavailable, match="Database unavailable"):
        await store.check_and_record("key", "POST:/incidents", 10)
