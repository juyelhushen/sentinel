from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from sentinel.application.ports.tool_execution_repository import ToolExecutionRepository
from sentinel.domain.tool_execution import ToolExecution
from sentinel.infrastructure.database.postgres import (
    PostgreSQLDatabase,
    postgres_transaction,
)
from sentinel.tools.models import ToolExecutionStatus


class PostgreSQLToolExecutionRepository(ToolExecutionRepository):
    def __init__(self, database: PostgreSQLDatabase) -> None:
        self._database = database

    async def save(
        self,
        tool_execution: ToolExecution,
        connection: AsyncConnection[dict[str, Any]] | None = None,
    ) -> None:
        async with postgres_transaction(self._database, connection) as transaction:
            await self._save(tool_execution, transaction)

    @staticmethod
    async def _save(
        record: ToolExecution, connection: AsyncConnection[dict[str, Any]]
    ) -> None:
        await connection.execute(
            """
            INSERT INTO tool_executions (
                request_id, tool_name, status, execution_id, arguments,
                output, error, started_at, completed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record.request_id,
                record.tool_name,
                record.status.value,
                record.execution_id,
                Jsonb(record.arguments),
                record.output,
                record.error,
                record.started_at,
                record.completed_at,
            ),
        )

    async def get_by_execution_id(self, execution_id: UUID) -> list[ToolExecution]:
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                "SELECT * FROM tool_executions WHERE execution_id = %s ORDER BY started_at ASC",
                (execution_id,),
            )
            rows = await cursor.fetchall()
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: dict[str, Any]) -> ToolExecution:
        return ToolExecution(
            request_id=row["request_id"],
            tool_name=row["tool_name"],
            status=ToolExecutionStatus(row["status"]),
            execution_id=row["execution_id"],
            arguments=row["arguments"],
            output=row["output"],
            error=row["error"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )
