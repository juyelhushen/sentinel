from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.models.incident import Incident
from sentinel.workflows.nodes.execution import execution_start_node


def test_execution_start_node_creates_running_execution() -> None:

    incident= Incident(
        title="Tests are failing",
        description="Several tests are failing",
        repository="sentinel"
    )

    result = execution_start_node(
        {
            "incident": incident,
            "execution": None,
            "plan": None,
            "investigation": None,
            "error": None,
        }
    )

    execution = result["execution"]

    assert execution is not None
    assert execution.incident_id == incident.id
    assert execution.status == ExecutionStatus.RUNNING
    assert execution.started_at is not None

    assert len(incident.executions) == 1
    assert incident.executions[0] == execution