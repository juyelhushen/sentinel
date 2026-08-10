from enum import StrEnum


class TaskStatus(StrEnum):
    """Lifecycle states for a planned task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
