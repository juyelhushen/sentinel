import hashlib
import logging
from typing import Any

from psycopg import AsyncConnection
from psycopg import Error as PostgreSQLError

from sentinel.infrastructure.database.postgres import (
    DatabaseUnavailable,
    PostgreSQLDatabase,
)

logger = logging.getLogger(__name__)

RATE_LIMIT_CLEANUP_INTERVAL_SECONDS = 60
RATE_LIMIT_CLEANUP_BATCH_SIZE = 500


class PostgreSQLRateLimitStore:
    """Atomically store sliding-window requests in the shared PostgreSQL database."""

    def __init__(self, database: PostgreSQLDatabase) -> None:
        self._database = database

    async def check_and_record(
        self,
        api_key: str,
        endpoint: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> int | None:
        key_hash = hashlib.sha256(api_key.encode("utf-8")).digest()
        lock_key = f"{key_hash.hex()}:{endpoint}"
        try:
            async with self._database.connection() as connection:
                await self._cleanup_expired_requests(connection)
                await connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (lock_key,),
                )
                cursor = await connection.execute(
                    """
                    SELECT COUNT(*) AS request_count,
                           GREATEST(
                               1,
                               CEIL(EXTRACT(EPOCH FROM (
                                   MIN(requested_at)
                                   + (%s * INTERVAL '1 second')
                                   - clock_timestamp()
                               )))::integer
                           ) AS retry_after
                    FROM rate_limit_requests
                    WHERE api_key_hash = %s
                      AND endpoint = %s
                      AND requested_at > clock_timestamp()
                          - (%s * INTERVAL '1 second')
                    """,
                    (window_seconds, key_hash, endpoint, window_seconds),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise RuntimeError("Rate-limit count query returned no row.")
                if row["request_count"] >= max_requests:
                    return int(row["retry_after"])
                await connection.execute(
                    """
                    INSERT INTO rate_limit_requests (
                        api_key_hash, endpoint, requested_at, expires_at
                    ) VALUES (
                        %s, %s, clock_timestamp(),
                        clock_timestamp() + (%s * INTERVAL '1 second')
                    )
                    """,
                    (key_hash, endpoint, window_seconds),
                )
                return None
        except DatabaseUnavailable:
            raise
        except PostgreSQLError as error:
            logger.error(
                "PostgreSQL rate-limit storage failed (%s); request denied.",
                type(error).__name__,
            )
            raise DatabaseUnavailable(
                "Rate limiting is temporarily unavailable."
            ) from None

    async def _cleanup_expired_requests(
        self, connection: AsyncConnection[dict[str, Any]]
    ) -> None:
        lock_cursor = await connection.execute(
            "SELECT pg_try_advisory_xact_lock(1397050964, 1) AS acquired"
        )
        lock_result = await lock_cursor.fetchone()
        if lock_result is None:
            raise DatabaseUnavailable("Rate limiting is temporarily unavailable.")
        if not lock_result["acquired"]:
            return

        state_cursor = await connection.execute(
            """
            SELECT last_cleanup_at IS NULL OR last_cleanup_at <=
                   clock_timestamp() - (%s * INTERVAL '1 second') AS due
            FROM rate_limit_cleanup_state
            WHERE singleton_id = 1
            FOR UPDATE
            """,
            (RATE_LIMIT_CLEANUP_INTERVAL_SECONDS,),
        )
        state = await state_cursor.fetchone()
        if state is None:
            raise DatabaseUnavailable("Rate limiting is temporarily unavailable.")
        if not state["due"]:
            return

        await connection.execute(
            """
            WITH expired_rows AS (
                SELECT ctid
                FROM rate_limit_requests
                WHERE expires_at <= clock_timestamp()
                ORDER BY expires_at
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            DELETE FROM rate_limit_requests AS requests
            USING expired_rows
            WHERE requests.ctid = expired_rows.ctid
            """,
            (RATE_LIMIT_CLEANUP_BATCH_SIZE,),
        )
        await connection.execute(
            """
            UPDATE rate_limit_cleanup_state
            SET last_cleanup_at = clock_timestamp()
            WHERE singleton_id = 1
            """
        )
