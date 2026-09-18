from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.models.execution import Execution
from sentinel.workflows.graph_state import SentinelGraphState


def execution_start_node(
    state: SentinelGraphState,
) -> dict:
    """Create or start the execution for the workflow."""

    incident = state["incident"]
    execution = state.get("execution")

    if execution is None:
        execution = Execution(
            incident_id=incident.id,
        )

        incident.add_execution(execution)

    if execution.status == ExecutionStatus.PENDING:
        execution.start()

    return {
        "execution": execution,
        "error": state.get("error"),
    }
