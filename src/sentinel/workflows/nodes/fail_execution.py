from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.enums.incident_status import IncidentStatus
from sentinel.workflows.graph_state import SentinelGraphState


def execution_fail_node(
    state: SentinelGraphState,
) -> dict:
    """Mark the current execution as failed."""

    execution = state.get("execution")

    if execution is None:
        incident = state.get("incident")
        if incident is not None and incident.status not in {
            IncidentStatus.COMPLETED,
            IncidentStatus.FAILED,
            IncidentStatus.CANCELLED,
        }:
            incident.fail()
        return {
            "execution": None,
            "error": state.get("error"),
        }

    if execution.status == ExecutionStatus.RUNNING:
        execution.fail()

    incident = state.get("incident")
    if incident is not None and incident.status not in {
        IncidentStatus.COMPLETED,
        IncidentStatus.FAILED,
        IncidentStatus.CANCELLED,
    }:
        incident.fail()

    error = state.get("error")
    if error is None and state.get("repair_enabled"):
        error = "Repair verification failed or the retry limit was exhausted."

    return {
        "execution": execution,
        "error": error,
    }
