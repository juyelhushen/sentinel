import hashlib
import logging

from psycopg import Error as PostgreSQLError

from sentinel.infrastructure.database.postgres import (
    DatabaseUnavailable,
    PostgreSQLDatabase,
)

logger = logging.getLogger(__name__)


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
                await connection.execute(
                    "DELETE FROM rate_limit_requests "
                    "WHERE expires_at <= clock_timestamp()"
                )
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
