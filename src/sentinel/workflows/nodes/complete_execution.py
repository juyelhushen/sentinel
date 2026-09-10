from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.workflows.graph_state import SentinelGraphState


def execution_complete_node(
        state: SentinelGraphState
) -> dict :
    """Complete the current execution."""

    execution = state['execution']

    if execution is None:
        raise ValueError("Cannot complete workflow without an execution.")

    if execution.status != ExecutionStatus.RUNNING:
        raise ValueError("Cannot complete an execution that is not running.")

    execution.complete()

    return {
        "execution": execution,
        "error": None,
    }