import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sentinel.application.ports.incident_repository import (
    IncidentRepository,
)
from sentinel.domain.enums.incident_status import IncidentStatus
from sentinel.domain.models.incident import Incident


class SQLiteIncidentRepository(IncidentRepository):
    """SQLite implementation of the incident repository."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def save(self, incident: Incident) -> None:
        """Insert or update an incident."""

        self._connection.execute(
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

        self._connection.commit()

    def get(self, incident_id: UUID) -> Incident | None:
        """Retrieve an incident by ID."""

        row = self._connection.execute(
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
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )