from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from sentinel.domain.models.execution import Execution
from sentinel.domain.models.incident import Incident
from sentinel.domain.tool_execution import ToolExecution
from sentinel.infrastructure.persistence.postgres.execution_repository import (
    PostgreSQLExecutionRepository,
)
from sentinel.infrastructure.persistence.postgres.incident_repository import (
    PostgreSQLIncidentRepository,
)
from sentinel.infrastructure.persistence.postgres.tool_execution_repository import (
    PostgreSQLToolExecutionRepository,
)
from sentinel.tools.models import ToolExecutionStatus


@pytest.mark.parametrize(
    "record_type,repository_type",
    [
        (Incident, PostgreSQLIncidentRepository),
        (Execution, PostgreSQLExecutionRepository),
        (ToolExecution, PostgreSQLToolExecutionRepository),
    ],
)
async def test_injected_postgres_connection_is_reused_without_commit(
    record_type, repository_type
) -> None:
    if record_type is Incident:
        record = Incident(
            title="Failure", description="Tests failed", repository="test"
        )
    elif record_type is Execution:
        record = Execution(incident_id=uuid4())
    else:
        record = ToolExecution(
            tool_name="read_file",
            status=ToolExecutionStatus.SUCCESS,
            arguments={"path": "example.txt"},
        )
    database = Mock()
    connection = AsyncMock()
    await repository_type(database).save(record, connection)
    database.connection.assert_not_called()
    connection.commit.assert_not_awaited()
    connection.rollback.assert_not_awaited()
    connection.close.assert_not_awaited()
    statement, parameters = connection.execute.await_args.args
    assert "%s" in statement
    assert "?" not in statement
    if record_type is ToolExecution:
        assert isinstance(parameters[4], Jsonb)
        assert parameters[4].obj == record.arguments
    else:
        assert parameters[0] == record.id


async def test_postgres_incident_native_row_mapping() -> None:
    incident = Incident(title="Failure", description="Tests failed", repository="test")
    row = {
        "id": incident.id,
        "title": incident.title,
        "description": incident.description,
        "repository": incident.repository,
        "status": incident.status.value,
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
    }
    cursor = AsyncMock()
    cursor.fetchone.side_effect = [row, None]
    connection = AsyncMock()
    connection.execute.return_value = cursor
    context = AsyncMock()
    context.__aenter__.return_value = connection
    database = Mock()
    database.connection.return_value = context
    repository = PostgreSQLIncidentRepository(database)
    result = await repository.get_by_id(incident.id)
    assert result is not None
    assert result.id == incident.id
    assert result.created_at == incident.created_at
    assert result.title == incident.title
    assert result.status == incident.status
    assert await repository.get(uuid4()) is None
    assert context.__aexit__.await_count == 2


async def test_execution_query_preserves_sqlite_null_timestamp_ordering() -> None:
    cursor = AsyncMock()
    cursor.fetchall.return_value = []
    connection = AsyncMock()
    connection.execute.return_value = cursor
    context = AsyncMock()
    context.__aenter__.return_value = connection
    database = Mock()
    database.connection.return_value = context
    repository = PostgreSQLExecutionRepository(database)
    incident_id = uuid4()

    assert await repository.get_by_incident_id(incident_id) == []
    connection.execute.assert_awaited_once_with(
        "SELECT * FROM executions WHERE incident_id = %s ORDER BY started_at ASC NULLS FIRST",
        (incident_id,),
    )
