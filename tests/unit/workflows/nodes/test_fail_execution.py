from uuid import uuid4

from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.models.execution import Execution
from sentinel.domain.models.incident import Incident
from sentinel.workflows.graph_state import SentinelGraphState
from sentinel.workflows.nodes.fail_execution import execution_fail_node


def test_execution_fail_node_marks_running_execution_as_failed() -> None:
    incident_id = uuid4()

    execution = Execution(
        incident_id=incident_id,
    )

    execution.start()

    incident = Incident(
        title="Tests are failing",
        description="Several tests are failing.",
        repository="sentinel",
    )

    state: SentinelGraphState = {
        "incident": incident,
        "execution": execution,
        "plan": None,
        "investigation": None,
        "error": "Planner failed.",
    }

    result = execution_fail_node(state)

    assert result["execution"] is execution
    assert result["error"] == "Planner failed."
    assert execution.status == ExecutionStatus.FAILED
    assert execution.completed_at is not None


def test_execution_fail_node_propagates_failure() -> None:
    incident_id = uuid4()

    execution = Execution(
        incident_id=incident_id,
    )

    execution.start()

    incident = Incident(
        title="Tests are failing",
        description="Several tests are failing.",
        repository="sentinel",
    )

    state: SentinelGraphState = {
        "incident": incident,
        "execution": execution,
        "plan": None,
        "investigation": None,
        "error": "Planner failed.",
    }

    result = execution_fail_node(state)

    assert result["execution"] is execution
    assert result["error"] == "Planner failed."
    assert execution.status == ExecutionStatus.FAILED
    assert execution.completed_at is not None


def test_execution_fail_node_handles_missing_execution() -> None:
    incident = Incident(
        title="Tests are failing",
        description="Several tests are failing.",
        repository="sentinel",
    )

    state: SentinelGraphState = {
        "incident": incident,
        "execution": None,
        "plan": None,
        "investigation": None,
        "error": "Planner failed.",
    }

    result = execution_fail_node(state)

    assert result.get("execution") is None
    assert result["error"] == "Planner failed."
