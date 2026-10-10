from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.enums.incident_status import IncidentStatus
from sentinel.workflows.graph_state import SentinelGraphState


def execution_complete_node(
    state: SentinelGraphState,
) -> dict:
    """Complete the current execution."""

    execution = state.get("execution")

    if execution is None:
        raise ValueError("Cannot complete workflow without an execution.")

    if state.get("repair_enabled"):
        verification = state.get("verification")
        if verification is None or not verification.passed:
            raise ValueError(
                "Cannot complete repair workflow without passing verification."
            )

        incident = state["incident"]
        if incident.status == IncidentStatus.INVESTIGATING:
            incident.begin_verification()
        if incident.status == IncidentStatus.VERIFYING:
            incident.complete()

    if execution.status == ExecutionStatus.RUNNING:
        execution.complete()

    return {
        "execution": execution,
        "error": state.get("error"),
    }
