import json
import sqlite3
from datetime import datetime
from uuid import UUID

from sentinel.application.ports.tool_execution_repository import ToolExecutionRepository
from sentinel.domain.tool_execution import ToolExecution
from sentinel.infrastructure.database.sqlite import SQLiteDatabase
from sentinel.tools.models import ToolExecutionStatus


class SQLiteToolExecutionRepository(ToolExecutionRepository):
    """SQLite persistence for tool execution audit records."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    async def save(
        self,
        tool_execution: ToolExecution,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        """Persist a tool execution."""


        if connection is not None:
            connection.execute(...)
            return

        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO tool_executions (
                    request_id,
                    tool_name,
                    status,
                    execution_id,
                    arguments,
                    output,
                    error,
                    started_at,
                    completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(tool_execution.request_id),
                    tool_execution.tool_name,
                    tool_execution.status.value,
                    (
                        str(tool_execution.execution_id)
                        if tool_execution.execution_id
                        else None
                    ),
                    json.dumps(tool_execution.arguments),
                    tool_execution.output,
                    tool_execution.error,
                    tool_execution.started_at.isoformat(),
                    (
                        tool_execution.completed_at.isoformat()
                        if tool_execution.completed_at
                        else None
                    ),
                ),
            )

            # connection.commit()

    async def get_by_execution_id(self, execution_id: UUID) -> list[ToolExecution]:
        """Return all tool executions belonging to an execution."""

        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                SELECT 
                    request_id,
                    tool_name,
                    status,
                    execution_id,
                    arguments,
                    output,
                    error,
                    started_at,
                    completed_at
                FROM tool_executions
                WHERE execution_id = ?
                ORDER BY started_at ASC
                """,
                (str(execution_id),),
            )

            rows = cursor.fetchall()

        return [self._row_to_tool_execution(row) for row in rows]

    @staticmethod
    def _row_to_tool_execution(
        row: tuple,
    ) -> ToolExecution:
        """Convert a SQLite row into a ToolExecution domain object."""

        return ToolExecution(
            request_id=UUID(row[0]),
            tool_name=row[1],
            status=ToolExecutionStatus(row[2]),
            execution_id=UUID(row[3]) if row[3] else None,
            arguments=json.loads(row[4]),
            output=row[5],
            error=row[6],
            started_at=datetime.fromisoformat(row[7]),
            completed_at=(datetime.fromisoformat(row[8]) if row[8] else None),
        )
