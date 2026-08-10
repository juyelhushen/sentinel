import sqlite3

from sentinel.domain.models.incident import Incident
from sentinel.infrastructure.persistence.models import initialize_database
from sentinel.infrastructure.persistence.sqlite_incident_repository import (
    SQLiteIncidentRepository,
)


def test_sqlite_repository_persists_incident() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    initialize_database(connection)

    repository = SQLiteIncidentRepository(connection)

    incident = Incident(
        title="Database failure",
        description="Database connection is unavailable",
        repository="/workspace/service",
    )

    repository.save(incident)

    result = repository.get(incident.id)

    assert result is not None
    assert result.id == incident.id
    assert result.title == incident.title
    assert result.description == incident.description
    assert result.repository == incident.repository
    assert result.status == incident.status

    connection.close()
