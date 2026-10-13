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
    *,
    request_count: int = 0,
    retry_after: int = 1,
    cleanup_acquired: bool = True,
    cleanup_due: bool = True,
    cleanup_error: Exception | None = None,
    cleanup_delete_error: Exception | None = None,
) -> tuple[PostgreSQLRateLimitStore, AsyncMock]:
    database = PostgreSQLDatabase("postgresql://example.invalid/db")
    lock_cursor = AsyncMock()
    lock_cursor.fetchone.return_value = {"acquired": cleanup_acquired}
    state_cursor = AsyncMock()
    state_cursor.fetchone.return_value = {"due": cleanup_due}
    count_cursor = AsyncMock()
    count_cursor.fetchone.return_value = {
        "request_count": request_count,
        "retry_after": retry_after,
    }
    connection = AsyncMock()

    async def execute(query: str, params: tuple[object, ...] | None = None):
        if "pg_try_advisory_xact_lock" in query:
            if cleanup_error is not None:
                raise cleanup_error
            return lock_cursor
        if "last_cleanup_at" in query:
            return state_cursor
        if "WITH expired_rows" in query and cleanup_delete_error is not None:
            raise cleanup_delete_error
        if "SELECT COUNT(*)" in query:
            return count_cursor
        return None

    connection.execute.side_effect = execute
    context = AsyncMock()
    context.__aenter__.return_value = connection
    database.connection = Mock(return_value=context)
    return PostgreSQLRateLimitStore(database), connection


async def test_rate_limit_store_hashes_key_and_cleans_expired_records() -> None:
    store, connection = _store_with_connection()
    raw_key = "raw-private-api-key"

    assert await store.check_and_record(raw_key, "POST:/incidents", 10) is None

    calls = connection.execute.await_args_list
    delete = next(call for call in calls if "WITH expired_rows" in call.args[0])
    assert "expires_at <= clock_timestamp()" in delete.args[0]
    assert "ORDER BY expires_at" in delete.args[0]
    assert "LIMIT %s" in delete.args[0]
    assert delete.args[1] == (500,)
    assert any("pg_try_advisory_xact_lock" in call.args[0] for call in calls)
    assert any("pg_advisory_xact_lock" in call.args[0] for call in calls)
    assert raw_key not in repr(calls)
    count_call = next(call for call in calls if "SELECT COUNT(*)" in call.args[0])
    assert count_call.args[1] == (
        60,
        hashlib.sha256(raw_key.encode()).digest(),
        "POST:/incidents",
        60,
    )
    insert = next(
        call for call in calls if "INSERT INTO rate_limit_requests" in call.args[0]
    )
    assert insert.args[1] == (
        hashlib.sha256(raw_key.encode()).digest(),
        "POST:/incidents",
        60,
    )


async def test_rate_limit_store_returns_retry_after_without_insert() -> None:
    store, connection = _store_with_connection(request_count=2, retry_after=23)

    assert await store.check_and_record("key", "GET:/health", 2) == 23
    calls = connection.execute.await_args_list
    assert any("WITH expired_rows" in call.args[0] for call in calls)
    assert any("SELECT COUNT(*)" in call.args[0] for call in calls)
    assert not any("INSERT INTO rate_limit_requests" in call.args[0] for call in calls)


async def test_cleanup_is_throttled_when_interval_is_not_due() -> None:
    store, connection = _store_with_connection(cleanup_due=False)

    async with store._database.connection() as pooled_connection:
        await store._cleanup_expired_requests(pooled_connection)

    calls = connection.execute.await_args_list
    assert len(calls) == 2
    assert "pg_try_advisory_xact_lock" in calls[0].args[0]
    assert "last_cleanup_at" in calls[1].args[0]
    assert not any("WITH expired_rows" in call.args[0] for call in calls)


async def test_cleanup_skips_when_another_instance_holds_the_lock() -> None:
    store, connection = _store_with_connection(cleanup_acquired=False)

    async with store._database.connection() as pooled_connection:
        await store._cleanup_expired_requests(pooled_connection)

    calls = connection.execute.await_args_list
    assert len(calls) == 1
    assert "pg_try_advisory_xact_lock" in calls[0].args[0]


async def test_cleanup_failure_fails_closed_without_rate_count(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store, connection = _store_with_connection(
        cleanup_error=OperationalError("private cleanup details")
    )

    with caplog.at_level(logging.ERROR), pytest.raises(DatabaseUnavailable) as error:
        await store.check_and_record("key", "POST:/incidents", 1)

    assert str(error.value) == "Rate limiting is temporarily unavailable."
    assert "OperationalError" in caplog.text
    assert "private cleanup details" not in caplog.text
    assert not any(
        "SELECT COUNT(*)" in call.args[0] for call in connection.execute.await_args_list
    )


async def test_expired_row_delete_failure_fails_closed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store, connection = _store_with_connection(
        cleanup_delete_error=OperationalError("private cleanup details")
    )

    with caplog.at_level(logging.ERROR), pytest.raises(DatabaseUnavailable) as error:
        await store.check_and_record("key", "POST:/incidents", 1)

    assert str(error.value) == "Rate limiting is temporarily unavailable."
    assert "OperationalError" in caplog.text
    assert "private cleanup details" not in caplog.text
    assert not any(
        "SELECT COUNT(*)" in call.args[0] for call in connection.execute.await_args_list
    )


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
