from sentinel.domain.models.execution import Execution
from sentinel.domain.models.incident import Incident
from sentinel.infrastructure.database.schema import SchemaInitializer
from sentinel.infrastructure.database.sqlite import SQLiteDatabase
from sentinel.infrastructure.persistence.sqllite.execution_repository import SQLiteExecutionRepository
from sentinel.infrastructure.persistence.sqllite.incident_repository import SQLiteIncidentRepository

async def test_incident_and_execution_share_transaction(tmp_path):
    database = SQLiteDatabase(tmp_path / "sentinel.db")
    SchemaInitializer(database).initialize()

    incident_repository = SQLiteIncidentRepository(database)
    execution_repository = SQLiteExecutionRepository(database)

    incident = Incident(
        title="Database failure",
        description="Test incident",
        repository="test-repo",
    )

    execution = Execution(incident_id=incident.id)

    with database.transaction() as connection:
        await incident_repository.save(
            incident,
            connection=connection,
        )

        await execution_repository.save(
            execution,
            connection=connection,
        )

    saved_incident = await incident_repository.get_by_id(incident.id)
    saved_execution = await execution_repository.get_by_id(execution.id)

    assert saved_incident is not None
    assert saved_execution is not None
    assert saved_execution.incident_id == incident.id