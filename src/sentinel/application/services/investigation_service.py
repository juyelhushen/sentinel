from uuid import UUID

from sentinel.application.ports.execution_repository import ExecutionRepository
from sentinel.application.ports.incident_repository import IncidentRepository
from sentinel.domain.models.execution import Execution
from sentinel.domain.models.incident import Incident
from sentinel.workflows.graph_state import SentinelGraphState


class InvestigationService:
    """Application service for running incident investigations."""

    def __init__(
        self,
        incident_repository: IncidentRepository,
        execution_repository: ExecutionRepository,
        graph,
    ) -> None:
        self._incident_repository = incident_repository
        self._execution_repository = execution_repository
        self._graph = graph

    async def investigate(
        self,
        incident_id: UUID,
    ) -> SentinelGraphState:
        """Run an investigation for an incident."""

        incident = await self._get_incident(incident_id)

        execution = Execution(
            incident_id=incident.id,
        )

        incident.start_investigation()
        incident.add_execution(execution)

        await self._incident_repository.save(incident)
        await self._execution_repository.save(execution)

        state = self._build_initial_state(
            incident=incident,
            execution=execution,
        )

        try:
            result = await self._graph.ainvoke(state)
        except Exception:
            execution.fail()
            incident.fail()

            await self._execution_repository.save(execution)
            await self._incident_repository.save(incident)

            raise

        execution = result.get("execution")

        if execution is None:
            raise RuntimeError("Workflow completed without an execution.")

        if result.get("error") is None:
            incident.begin_verification()
        else:
            incident.fail()

        await self._execution_repository.save(execution)
        await self._incident_repository.save(incident)

        result["execution"] = execution
        result["incident"] = incident

        return result

    async def _get_incident(
        self,
        incident_id: UUID,
    ) -> Incident:
        incident = await self._incident_repository.get_by_id(
            incident_id,
        )

        if incident is None:
            raise ValueError(f"Incident not found: {incident_id}")

        return incident

    @staticmethod
    def _build_initial_state(
        incident: Incident,
        execution: Execution,
    ) -> SentinelGraphState:
        return {
            "incident": incident,
            "execution": execution,
            "plan": None,
            "investigation": None,
            "error": None,
        }
