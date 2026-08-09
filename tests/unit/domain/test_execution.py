from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.models.execution import Execution


def test_execution_can_start_and_complete() -> None:
    execution = Execution(
        incident_id=__import__("uuid").uuid4(),
    )

    execution.start()

    assert execution.status == ExecutionStatus.RUNNING
    assert execution.started_at is not None

    execution.complete()

    assert execution.status == ExecutionStatus.COMPLETED
    assert execution.completed_at is not None