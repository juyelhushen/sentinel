from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from sentinel.application.ports.incident_repository import IncidentRepository
from sentinel.domain.enums.incident_status import IncidentStatus
from sentinel.domain.models.incident import Incident
from sentinel.infrastructure.database.postgres import (
    PostgreSQLDatabase,
    postgres_transaction,
)


class PostgreSQLIncidentRepository(IncidentRepository):
    def __init__(self, database: PostgreSQLDatabase) -> None:
        self._database = database

    async def save(
        self,
        incident: Incident,
        connection: AsyncConnection[dict[str, Any]] | None = None,
    ) -> None:
        async with postgres_transaction(self._database, connection) as transaction:
            await self._save(incident, transaction)

    @staticmethod
    async def _save(
        incident: Incident, connection: AsyncConnection[dict[str, Any]]
    ) -> None:
        await connection.execute(
            """
            INSERT INTO incidents (id, title, description, repository, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                repository = EXCLUDED.repository,
                status = EXCLUDED.status,
                updated_at = EXCLUDED.updated_at
            """,
            (
                incident.id,
                incident.title,
                incident.description,
                incident.repository,
                incident.status.value,
                incident.created_at,
                incident.updated_at,
            ),
        )

    async def get(self, incident_id: UUID) -> Incident | None:
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                "SELECT * FROM incidents WHERE id = %s", (incident_id,)
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: dict[str, Any]) -> Incident:
        return Incident(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            repository=row["repository"],
            status=IncidentStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
