from datetime import UTC, datetime, timedelta

from sentinel.domain.tool_execution import ToolExecution
from sentinel.tools.models import ToolExecutionStatus


class FakeToolExecutionRepository:
    def __init__(self):
        self.records = []

    async def save(self, tool_execution):
        self.records.append(tool_execution)


def test_duration_ms():
    started = datetime.now(UTC)
    completed = started + timedelta(milliseconds=250)

    execution = ToolExecution(
        tool_name="read_file",
        status=ToolExecutionStatus.SUCCESS,
        started_at=started,
        completed_at=completed,
    )

    assert execution.duration_ms == 250


def test_duration_is_none_when_not_completed():
    execution = ToolExecution(
        tool_name="read_file",
        status=ToolExecutionStatus.SUCCESS,
    )

    assert execution.duration_ms is None
