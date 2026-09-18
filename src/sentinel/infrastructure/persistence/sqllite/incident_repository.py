import sqlite3
from pathlib import Path
from uuid import UUID

from sentinel.application.ports.incident_repository import (
    IncidentRepository,
)
from sentinel.domain.enums.incident_status import IncidentStatus
from sentinel.domain.models.incident import Incident


class SQLiteIncidentRepository(IncidentRepository):
    """SQLite implementation of the incident repository."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    async def initialize(self) -> None:
        """Create the incidents table."""

        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            connection.commit()

    async def save(self, incident: Incident) -> None:
        """Insert or update an incident."""

        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO incidents (
                    id,
                    title,
                    description,
                    repository,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    repository = excluded.repository,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    str(incident.id),
                    incident.title,
                    incident.description,
                    incident.repository,
                    incident.status.value,
                    incident.created_at.isoformat(),
                    incident.updated_at.isoformat(),
                ),
            )

            connection.commit()

    async def get(
        self,
        incident_id: UUID,
    ) -> Incident | None:
        """Retrieve an incident."""

        with sqlite3.connect(self._database_path) as connection:
            connection.row_factory = sqlite3.Row

            row = connection.execute(
                """
                SELECT
                    id,
                    title,
                    description,
                    repository,
                    status,
                    created_at,
                    updated_at
                FROM incidents
                WHERE id = ?
                """,
                (str(incident_id),),
            ).fetchone()

        if row is None:
            return None

        return Incident(
            id=UUID(row["id"]),
            title=row["title"],
            description=row["description"],
            repository=row["repository"],
            status=IncidentStatus(row["status"]),
            created_at=__import__("datetime").datetime.fromisoformat(row["created_at"]),
            updated_at=__import__("datetime").datetime.fromisoformat(row["updated_at"]),
        )
