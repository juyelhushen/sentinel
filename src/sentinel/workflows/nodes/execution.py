from sentinel.domain.models.execution import Execution
from sentinel.workflows.graph_state import SentinelGraphState


def execution_start_node(
        state: SentinelGraphState
) -> dict:
    """Create and start an execution for the incident."""

    incident = state['incident']

    execution = Execution(
        incident_id=incident.id
    )

    execution.start()

    incident.add_execution(execution)

    return {
        "execution" : execution,
        "error" : None
    }