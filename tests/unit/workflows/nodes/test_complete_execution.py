from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.models.execution import Execution
from sentinel.domain.models.incident import Incident
from sentinel.workflows.nodes.complete_execution import execution_complete_node


def test_execution_complete_node_completes_execution() -> None:
    incident = Incident(
        title="Tests are failing",
        description="Several tests are failing.",
        repository="sentinel",
    )

    execution = Execution(
        incident_id=incident.id,
    )

    execution.start()

    result = execution_complete_node(
        {
            "incident": incident,
            "execution": execution,
            "plan": None,
            "investigation": None,
            "error": None,
        }
    )

    assert result["execution"].status == ExecutionStatus.COMPLETED
    assert result["execution"].completed_at is not None


def test_execution_complete_node_rejects_missing_execution() -> None:
    incident = Incident(
        title="Tests are failing",
        description="Several tests are failing.",
        repository="sentinel",
    )

    try:
        execution_complete_node(
            {
                "incident": incident,
                "execution": None,
                "plan": None,
                "investigation": None,
                "error": None,
            }
        )
    except ValueError as exc:
        assert str(exc) == "Cannot complete workflow without an execution."
    else:
        raise AssertionError("Expected ValueError")