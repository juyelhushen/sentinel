from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from sentinel.application.ports.execution_repository import ExecutionRepository
from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.models.execution import Execution
from sentinel.infrastructure.database.postgres import (
    PostgreSQLDatabase,
    postgres_transaction,
)


class PostgreSQLExecutionRepository(ExecutionRepository):
    def __init__(self, database: PostgreSQLDatabase) -> None:
        self._database = database

    async def save(
        self,
        execution: Execution,
        connection: AsyncConnection[dict[str, Any]] | None = None,
    ) -> None:
        async with postgres_transaction(self._database, connection) as transaction:
            await self._save(execution, transaction)

    @staticmethod
    async def _save(
        execution: Execution, connection: AsyncConnection[dict[str, Any]]
    ) -> None:
        await connection.execute(
            """
            INSERT INTO executions (id, incident_id, status, started_at, completed_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                started_at = EXCLUDED.started_at,
                completed_at = EXCLUDED.completed_at
            """,
            (
                execution.id,
                execution.incident_id,
                execution.status.value,
                execution.started_at,
                execution.completed_at,
            ),
        )

    async def get_by_id(self, execution_id: UUID) -> Execution | None:
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                "SELECT * FROM executions WHERE id = %s", (execution_id,)
            )
            row = await cursor.fetchone()
        return self._to_domain(row) if row is not None else None

    async def get_by_incident_id(self, incident_id: UUID) -> list[Execution]:
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                "SELECT * FROM executions WHERE incident_id = %s ORDER BY started_at ASC NULLS FIRST",
                (incident_id,),
            )
            rows = await cursor.fetchall()
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: dict[str, Any]) -> Execution:
        return Execution(
            id=row["id"],
            incident_id=row["incident_id"],
            status=ExecutionStatus(row["status"]),
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )
