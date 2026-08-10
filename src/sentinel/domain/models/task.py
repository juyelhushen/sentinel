from dataclasses import dataclass, field
from uuid import UUID, uuid4

from sentinel.domain.enums.task_status import TaskStatus


@dataclass
class Task:
    """A single unit of work within an incident plan."""

    title: str
    description: str
    id: UUID = field(default_factory=uuid4)
    status: TaskStatus = TaskStatus.PENDING

    def start(self) -> None:
        """Mark the task as in progress."""
        if self.status != TaskStatus.PENDING:
            raise ValueError(f"Cannot start task in status: {self.status}")

        self.status = TaskStatus.IN_PROGRESS

    def complete(self) -> None:
        """Mark the task as completed."""
        if self.status != TaskStatus.IN_PROGRESS:
            raise ValueError(f"Cannot complete task in status: {self.status}")

        self.status = TaskStatus.COMPLETED

    def fail(self) -> None:
        """Mark the task as failed."""
        self.status = TaskStatus.FAILED
