from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.models.plan import Plan


@dataclass
class Execution:
    """Represents one attempt to resolve an incident."""

    incident_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: ExecutionStatus = ExecutionStatus.PENDING
    plan: Plan | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def start(self) -> None:
        """Start execution."""
        if self.status != ExecutionStatus.PENDING:
            raise ValueError(f"Cannot start execution in status: {self.status}")

        self.status = ExecutionStatus.RUNNING
        self.started_at = datetime.now(UTC)

    def complete(self) -> None:
        """Complete execution."""
        if self.status != ExecutionStatus.RUNNING:
            raise ValueError(f"Cannot complete execution in status: {self.status}")

        self.status = ExecutionStatus.COMPLETED
        self.completed_at = datetime.now(UTC)

    def fail(self) -> None:
        """Mark execution as failed."""
        self.status = ExecutionStatus.FAILED
        self.completed_at = datetime.now(UTC)
