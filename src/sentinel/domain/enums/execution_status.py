from enum import StrEnum


class ExecutionStatus(StrEnum):
    """Lifecycle states for an incident execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
