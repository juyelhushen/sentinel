from pathlib import Path

import pytest

from sentinel.bootstrap.application import create_sentinel_application
from sentinel.bootstrap.investigation import create_investigation_service
from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.enums.incident_status import IncidentStatus
from sentinel.domain.models.incident import Incident
from sentinel.infrastructure.database.sqlite import SQLiteDatabase
from sentinel.infrastructure.persistence.sqllite.execution_repository import (
    SQLiteExecutionRepository,
)
from sentinel.infrastructure.persistence.sqllite.incident_repository import (
    SQLiteIncidentRepository,
)
from sentinel.infrastructure.persistence.sqllite.tool_execution_repository import (
    SQLiteToolExecutionRepository,
)
from sentinel.llm.base import LLMProvider
from sentinel.llm.models import LLMRequest, LLMResponse


class FakeLLMProvider(LLMProvider):
    """Fake LLM provider for application integration tests."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="""
            {
                "summary": "Search for token validation.",
                "steps": [
                    {
                        "step_number": 1,
                        "action": "search_code",
                        "description": "Find token validation code.",
                        "arguments": {
                            "query": "validate_token"
                        }
                    }
                ]
            }
            """,
            model="fake-model",
        )

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_sentinel_application_runs_end_to_end(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "service.py"

    source_file.write_text(
        "def validate_token():\n    return True\n",
        encoding="utf-8",
    )

    application = create_sentinel_application(
        llm_provider=FakeLLMProvider(),
        repository_root=tmp_path,
    )

    incident = Incident(
        title="Token validation issue",
        description="Token validation may be failing.",
        repository="example-repository",
    )

    result = await application.ainvoke(
        {
            "incident": incident,
            "plan": None,
            "investigation": None,
            "error": None,
        }
    )

    assert result["error"] is None
    assert result["investigation"] is not None
    assert len(result["investigation"].step_results) == 1
    assert result["investigation"].step_results[0].success is True


@pytest.mark.asyncio
async def test_investigation_service_factory_persists_execution_and_audit(
    tmp_path: Path,
) -> None:
    (tmp_path / "service.py").write_text(
        "def validate_token():\n    return True\n", encoding="utf-8"
    )
    database_path = tmp_path / "sentinel.db"
    service = create_investigation_service(
        llm_provider=FakeLLMProvider(),
        repository_root=tmp_path,
        database_path=database_path,
    )
    database = SQLiteDatabase(database_path)
    incidents = SQLiteIncidentRepository(database)
    incident = Incident(
        title="Token validation issue",
        description="Token validation may be failing.",
        repository="example-repository",
    )
    await incidents.save(incident)

    result = await service.investigate(incident.id)

    assert result["error"] is None
    execution = result["execution"]
    assert execution is not None
    assert execution.status == ExecutionStatus.COMPLETED
    assert result["investigation"].step_results[0].success is True
    stored_incident = await incidents.get_by_id(incident.id)
    assert stored_incident is not None
    assert stored_incident.status == IncidentStatus.VERIFYING
    stored_execution = await SQLiteExecutionRepository(database).get_by_id(execution.id)
    assert stored_execution is not None
    assert stored_execution.status == ExecutionStatus.COMPLETED
    with database.connect() as connection:
        (request_id,) = connection.execute(
            "SELECT request_id FROM tool_executions"
        ).fetchone()
    assert request_id is not None
    assert (
        await SQLiteToolExecutionRepository(database).get_by_execution_id(execution.id)
        == []
    )
