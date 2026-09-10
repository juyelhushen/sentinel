from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.workflows.graph_state import SentinelGraphState


def execution_fail_node(state: SentinelGraphState) -> dict:
    """Mark the current execution as failed."""

    execution = state["execution"]

    if execution is None:
        return {
            "error": state["error"],
        }

    if execution.status == ExecutionStatus.RUNNING:
        execution.fail()

    return {
        "execution": execution,
        "error": state['error'],
    }

