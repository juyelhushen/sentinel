import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from psycopg import AsyncConnection, InterfaceError, OperationalError, ProgrammingError
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, PoolTimeout

logger = logging.getLogger(__name__)


def _sanitized_connection_error(error: Exception) -> str:
    message = str(error).casefold()
    diagnostics = (
        (r"authentication failed|no pg_hba.conf entry", "Authentication failed."),
        (
            (
                r"could not translate host name|name or service not known|"
                r"nodename nor servname|name resolution|getaddrinfo failed"
            ),
            "DNS resolution failed.",
        ),
        (
            r"\bssl\b|\btls\b|certificate",
            "TLS negotiation or certificate validation failed.",
        ),
        (r"database .* does not exist", "Requested database does not exist."),
        (
            (
                r"connection refused|network is unreachable|no route to host|"
                r"connection timed out|timeout expired|connection reset|server closed"
            ),
            "Network connection failed or timed out.",
        ),
    )
    for pattern, diagnostic in diagnostics:
        if re.search(pattern, message):
            return diagnostic
    if isinstance(error, PoolTimeout):
        return (
            "Timed out waiting for a pooled connection; underlying cause unavailable."
        )
    return "Connection failed; unrecognized driver details omitted."


class DatabaseUnavailable(RuntimeError):
    """A sanitized database configuration or connectivity failure."""


class PostgreSQLDatabase:
    """Own an asynchronous pool and transaction-scoped schema selection."""

    def __init__(
        self,
        database_url: str,
        *,
        schema: str = "sentinel",
        timeout_seconds: int = 10,
        pool_size: int = 5,
    ) -> None:
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,62}", schema):
            raise DatabaseUnavailable("Invalid PostgreSQL schema name.")
        if timeout_seconds < 1 or pool_size < 1:
            raise DatabaseUnavailable("Invalid database timeout or pool size.")
        try:
            parameters = conninfo_to_dict(database_url)
        except ValueError, ProgrammingError:
            raise DatabaseUnavailable(
                "Invalid PostgreSQL connection configuration."
            ) from None

        sslmode = parameters.get("sslmode", "require")
        local = parameters.get("host") in {"localhost", "127.0.0.1", "::1"}
        if sslmode not in {"require", "verify-ca", "verify-full"} and not (
            local and sslmode == "disable"
        ):
            raise DatabaseUnavailable("Remote PostgreSQL connections require TLS.")

        self.schema = schema
        self.timeout_seconds = timeout_seconds
        self._pool: AsyncConnectionPool[AsyncConnection[dict[str, Any]]] = (
            AsyncConnectionPool(
                conninfo=database_url,
                kwargs={
                    "row_factory": dict_row,
                    "connect_timeout": parameters.get(
                        "connect_timeout", timeout_seconds
                    ),
                    "sslmode": sslmode,
                    "prepare_threshold": None,
                },
                min_size=0,
                max_size=pool_size,
                open=False,
                timeout=timeout_seconds,
                reconnect_timeout=timeout_seconds,
            )
        )

    async def open(self) -> None:
        await self._pool.open()

    async def close(self) -> None:
        await self._pool.close()

    @asynccontextmanager
    async def connection(
        self, *, select_schema: bool = True
    ) -> AsyncIterator[AsyncConnection[dict[str, Any]]]:
        try:
            async with self._pool.connection(
                timeout=self.timeout_seconds
            ) as connection:
                if select_schema:
                    await connection.execute(
                        "SELECT set_config('search_path', %s, true)",
                        (f'"{self.schema}", pg_catalog',),
                    )
                yield connection
        except (OperationalError, InterfaceError, PoolTimeout) as error:
            logger.error(
                "PostgreSQL connection failed (%s): %s",
                type(error).__name__,
                _sanitized_connection_error(error),
            )
            raise DatabaseUnavailable(
                "Database unavailable. Check connectivity, TLS, and database credentials."
            ) from None


@asynccontextmanager
async def postgres_transaction(
    database: PostgreSQLDatabase,
    connection: AsyncConnection[dict[str, Any]] | None = None,
) -> AsyncIterator[AsyncConnection[dict[str, Any]]]:
    """Borrow a caller-owned connection or manage a pooled transaction."""
    if connection is not None:
        yield connection
    else:
        async with database.connection() as owned_connection:
            yield owned_connection
