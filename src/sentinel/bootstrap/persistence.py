import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from psycopg import Error

from sentinel.application.ports.execution_repository import ExecutionRepository
from sentinel.application.ports.incident_repository import IncidentRepository
from sentinel.application.ports.repair_repository import RepairRepository
from sentinel.application.ports.tool_execution_repository import ToolExecutionRepository
from sentinel.infrastructure.database.postgres import (
    DatabaseUnavailable,
    PostgreSQLDatabase,
)
from sentinel.infrastructure.database.postgres_schema import initialize_postgres_schema
from sentinel.infrastructure.database.schema import SchemaInitializer
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


@dataclass(frozen=True)
class Persistence:
    incidents: IncidentRepository
    executions: ExecutionRepository
    tool_executions: ToolExecutionRepository
    repairs: RepairRepository
    database: SQLiteDatabase | PostgreSQLDatabase


def resolve_database_path(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise DatabaseUnavailable("Expected a SQLite database URL.")
    path = Path(database_url.removeprefix(prefix)).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def create_database(
    database_url: str,
    *,
    schema: str = "sentinel",
    timeout_seconds: int = 10,
    pool_size: int = 5,
) -> SQLiteDatabase | PostgreSQLDatabase:
    if database_url.startswith("sqlite:///"):
        return SQLiteDatabase(resolve_database_path(database_url))
    if database_url.startswith(("postgresql://", "postgres://")):
        return PostgreSQLDatabase(
            database_url,
            schema=schema,
            timeout_seconds=timeout_seconds,
            pool_size=pool_size,
        )
    raise DatabaseUnavailable(
        "Unsupported database URL scheme. Use SQLite or PostgreSQL."
    )


def create_persistence(database: SQLiteDatabase | PostgreSQLDatabase) -> Persistence:
    if isinstance(database, PostgreSQLDatabase):
        return Persistence(
            PostgreSQLIncidentRepository(database),
            PostgreSQLExecutionRepository(database),
            PostgreSQLToolExecutionRepository(database),
            PostgreSQLRepairRepository(database),
            database=database,
        )
    return Persistence(
        SQLiteIncidentRepository(database),
        SQLiteExecutionRepository(database),
        SQLiteToolExecutionRepository(database),
        SQLiteRepairRepository(database),
        database=database,
    )


@asynccontextmanager
async def open_persistence(
    database_url: str,
    *,
    schema: str = "sentinel",
    timeout_seconds: int = 10,
    pool_size: int = 5,
) -> AsyncIterator[Persistence]:
    database = create_database(
        database_url,
        schema=schema,
        timeout_seconds=timeout_seconds,
        pool_size=pool_size,
    )
    if isinstance(database, PostgreSQLDatabase):
        try:
            await database.open()
            try:
                await initialize_postgres_schema(database)
            except Error:
                raise DatabaseUnavailable(
                    "Database schema initialization failed. Check database permissions and migration state."
                ) from None
            yield create_persistence(database)
        finally:
            await database.close()
    else:
        await asyncio.to_thread(SchemaInitializer(database).initialize)
        yield create_persistence(database)
