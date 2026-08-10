import sqlite3

from sentinel.application.ports.incident_repository import (
    IncidentRepository,
)
from sentinel.infrastructure.persistence.sqlite_incident_repository import (
    SQLiteIncidentRepository,
)


def create_incident_repository(
    connection: sqlite3.Connection,
) -> IncidentRepository:
    """Create the configured incident repository."""

    return SQLiteIncidentRepository(connection)
