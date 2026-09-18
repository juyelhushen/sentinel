import pytest

from sentinel.application.services.investigation_service import InvestigationService
from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.enums.incident_status import IncidentStatus
from sentinel.domain.models.incident import Incident


class FakeIncidentRepository:
    def __init__(self, incident):
        self.incident = incident
        self.saved = []

    async def save(self, incident):
        self.saved.append(incident)

    async def get_by_id(self, incident_id):
        if self.incident.id == incident_id:
            return self.incident

        return None


class FakeExecutionRepository:
    def __init__(self):
        self.saved = []

    async def save(self, execution):
        self.saved.append(execution)


class FakeGraph:
    async def ainvoke(self, state):
        execution = state["execution"]

        execution.start()
        execution.complete()

        return {
            **state,
            "execution": execution,
            "error": None,
        }


class FailingGraph:
    async def ainvoke(self, state):
        execution = state["execution"]

        execution.start()
        execution.fail()

        return {
            **state,
            "execution": execution,
            "error": "Planner failed.",
        }


async def test_successful_investigation():
    incident = Incident(
        title="Broken test",
        description="A test is failing.",
        repository="sentinel",
    )

    incident_repository = FakeIncidentRepository(incident)
    execution_repository = FakeExecutionRepository()

    service = InvestigationService(
        incident_repository=incident_repository,
        execution_repository=execution_repository,
        graph=FakeGraph(),
    )

    result = await service.investigate(incident.id)

    assert result["error"] is None

    assert result["execution"].status == (ExecutionStatus.COMPLETED)

    assert result["incident"].status == (IncidentStatus.VERIFYING)


async def test_failed_investigation():
    incident = Incident(
        title="Broken test",
        description="A test is failing.",
        repository="sentinel",
    )

    service = InvestigationService(
        incident_repository=FakeIncidentRepository(incident),
        execution_repository=FakeExecutionRepository(),
        graph=FailingGraph(),
    )

    result = await service.investigate(incident.id)

    assert result["execution"].status == (ExecutionStatus.FAILED)

    assert result["incident"].status == (IncidentStatus.FAILED)

    assert result["execution"].completed_at is not None


async def test_graph_exception_fails_execution():
    incident = Incident(
        title="Broken test",
        description="A test is failing.",
        repository="sentinel",
    )

    class ExplodingGraph:
        async def ainvoke(self, state):
            raise RuntimeError("Graph crashed.")

    execution_repository = FakeExecutionRepository()

    service = InvestigationService(
        incident_repository=FakeIncidentRepository(incident),
        execution_repository=execution_repository,
        graph=ExplodingGraph(),
    )

    with pytest.raises(RuntimeError, match="Graph crashed"):
        await service.investigate(incident.id)

    execution = execution_repository.saved[-1]

    assert execution.status == ExecutionStatus.FAILED
    assert execution.completed_at is not None
    assert incident.status == IncidentStatus.FAILED
