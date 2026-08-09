from enum import StrEnum


class IncidentStatus(StrEnum):
    """Lifecycle states for an engineering incident."""

    CREATED = "created"
    INVESTIGATING = "investigating"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"