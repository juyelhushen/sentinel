from uuid import uuid4

from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.enums.incident_status import IncidentStatus
from sentinel.domain.models.execution import Execution
from sentinel.domain.models.incident import Incident
from sentinel.infrastructure.database.schema import SchemaInitializer
from sentinel.infrastructure.database.sqlite import SQLiteDatabase
from sentinel.infrastructure.persistence.sqllite.execution_repository import SQLiteExecutionRepository
from sentinel.infrastructure.persistence.sqllite.incident_repository import (
    SQLiteIncidentRepository,
)


async def test_save_and_get_incident(tmp_path):

    database = SQLiteDatabase(tmp_path / "sentinel.db")
    SchemaInitializer(database).initialize()
    repository = SQLiteIncidentRepository(database)

    incident = Incident(
        id=uuid4(),
        title="Broken test",
        description="A test is failing.",
        repository="sentinel",
    )

    await repository.save(incident)

    result = await repository.get(incident.id)

    assert result is not None
    assert result.id == incident.id
    assert result.title == incident.title
    assert result.description == incident.description
    assert result.repository == incident.repository
    assert result.status == incident.status


async def test_save_updates_existing_incident(tmp_path):
    database = SQLiteDatabase(tmp_path / "sentinel.db")
    SchemaInitializer(database).initialize()
    repository = SQLiteIncidentRepository(database)

    incident = Incident(
        title="Broken test",
        description="A test is failing.",
        repository="sentinel",
    )

    await repository.save(incident)

    incident.start_investigation()

    await repository.save(incident)

    result = await repository.get(incident.id)

    assert result is not None
    assert result.status == IncidentStatus.INVESTIGATING
    

async def test_execution_lifecycle_is_persisted(tmp_path):
    database = SQLiteDatabase(tmp_path / "sentinel.db")
    SchemaInitializer(database).initialize()
    incident_repository = SQLiteIncidentRepository(database)
    execution_repository = SQLiteExecutionRepository(database)

    incident = Incident(
        title="Broken test",
        description="A test is failing.",
        repository="sentinel",
    )

    await incident_repository.save(incident)

    execution = Execution(
        incident_id=incident.id,
    )

    execution.start()

    await execution_repository.save(execution)

    execution.complete()

    await execution_repository.save(execution)

    result = await execution_repository.get_by_id(
        execution.id,
    )

    assert result is not None
    assert result.status == ExecutionStatus.COMPLETED
    assert result.started_at is not None
    assert result.completed_at is not None


async def test_get_executions_by_incident(tmp_path):
    database = SQLiteDatabase(tmp_path / "sentinel.db")
    SchemaInitializer(database).initialize()
    
    incident_repository = SQLiteIncidentRepository(database)
    execution_repository = SQLiteExecutionRepository(database)

    incident = Incident(
        title="Broken test",
        description="A test is failing.",
        repository="sentinel",
    )

    await incident_repository.save(incident)

    first = Execution(incident_id=incident.id)
    second = Execution(incident_id=incident.id)

    await execution_repository.save(first)
    await execution_repository.save(second)

    executions = await execution_repository.get_by_incident_id(
        incident.id,
    )

    assert len(executions) == 2
    assert {execution.id for execution in executions} == {
        first.id,
        second.id,
    }


async def test_execution_survives_repository_recreation(tmp_path):
    database = SQLiteDatabase(tmp_path / "sentinel.db")
    SchemaInitializer(database).initialize()
    incident_repository = SQLiteIncidentRepository(database)
    repository = SQLiteExecutionRepository(database)

    incident = Incident(
        title="Persistent incident",
        description="Test persistence.",
        repository="sentinel",
    )

    await incident_repository.save(incident)

    execution = Execution(
        incident_id=incident.id,
    )

    await repository.save(execution)

    new_repository = SQLiteExecutionRepository(database)

    result = await new_repository.get_by_id(
        execution.id,
    )

    assert result is not None
    assert result.id == execution.id
