import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sentinel.application.ports.execution_repository import (
    ExecutionRepository,
)
from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.models.execution import Execution
from sentinel.infrastructure.database.sqlite import SQLiteDatabase


class SQLiteExecutionRepository(ExecutionRepository):
    """SQLite implementation of the execution repository."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    async def save(
        self,
        execution: Execution,
    ) -> None:
        """Insert or update an execution."""

        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO executions (
                    id,
                    incident_id,
                    status,
                    started_at,
                    completed_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at
                """,
                (
                    str(execution.id),
                    str(execution.incident_id),
                    execution.status.value,
                    (
                        execution.started_at.isoformat()
                        if execution.started_at
                        else None
                    ),
                    (
                        execution.completed_at.isoformat()
                        if execution.completed_at
                        else None
                    ),
                ),
            )

            connection.commit()

    async def get_by_id(
        self,
        execution_id: UUID,
    ) -> Execution | None:
        """Retrieve an execution by ID."""

        with self._database.connect() as connection:
            connection.row_factory = sqlite3.Row

            row = connection.execute(
                """
                SELECT
                    id,
                    incident_id,
                    status,
                    started_at,
                    completed_at
                FROM executions
                WHERE id = ?
                """,
                (str(execution_id),),
            ).fetchone()

        if row is None:
            return None

        return self._to_domain(row)

    async def get_by_incident_id(
        self,
        incident_id: UUID,
    ) -> list[Execution]:
        """Retrieve all executions for an incident."""

        with self._database.connect() as connection:
            connection.row_factory = sqlite3.Row

            rows = connection.execute(
                """
                SELECT
                    id,
                    incident_id,
                    status,
                    started_at,
                    completed_at
                FROM executions
                WHERE incident_id = ?
                ORDER BY started_at ASC
                """,
                (str(incident_id),),
            ).fetchall()

        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: sqlite3.Row) -> Execution:
        """Convert a database row to an Execution."""

        return Execution(
            id=UUID(row["id"]),
            incident_id=UUID(row["incident_id"]),
            status=ExecutionStatus(row["status"]),
            started_at=(
                datetime.fromisoformat(row["started_at"]) if row["started_at"] else None
            ),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
        )
