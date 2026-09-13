from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sentinel.tools.models import ToolExecutionStatus


@dataclass(frozen=True)
class ToolExecution:
    """Records one tool execution for auditing and observability."""

    tool_name: str
    status: ToolExecutionStatus
    execution_id: UUID | None = None
    arguments: dict = field(default_factory=dict)
    output: str | None = None
    error: str | None = None
    request_id: UUID = field(default_factory=uuid4)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @property
    def duration_ms(self) -> float | None:
        """Return execution duration in milliseconds."""

        if self.completed_at is None:
            return None

        return (self.completed_at - self.started_at).total_seconds() * 1000
