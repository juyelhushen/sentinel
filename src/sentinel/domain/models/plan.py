from dataclasses import dataclass, field
from uuid import UUID, uuid4

from sentinel.domain.models.task import Task


@dataclass
class Plan:
    """Execution plan containing ordered engineering tasks."""

    tasks: list[Task] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)

    def add_task(self, task: Task) -> None:
        """Add a task to the plan."""
        self.tasks.append(task)

    def is_complete(self) -> bool:
        """Return whether every task has completed."""
        return bool(self.tasks) and all(
            task.status.value == "completed"
            for task in self.tasks
        )