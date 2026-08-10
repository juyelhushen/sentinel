from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sentinel.domain.enums.incident_status import IncidentStatus
from sentinel.domain.models.execution import Execution


@dataclass
class Incident:
    """Represents an engineering problem Sentinel must investigate."""

    title: str
    description: str
    repository: str
    id: UUID = field(default_factory=uuid4)
    status: IncidentStatus = IncidentStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    executions: list[Execution] = field(default_factory=list)

    def start_investigation(self) -> None:
        """Move the incident into investigation."""
        if self.status != IncidentStatus.CREATED:
            raise ValueError(f"Cannot investigate incident in status: {self.status}")

        self.status = IncidentStatus.INVESTIGATING
        self._touch()

    def add_execution(self, execution: Execution) -> None:
        """Attach an execution attempt to the incident."""
        if execution.incident_id != self.id:
            raise ValueError("Execution does not belong to this incident")

        self.executions.append(execution)
        self._touch()

    def complete(self) -> None:
        """Mark incident as successfully resolved."""
        if self.status != IncidentStatus.VERIFYING:
            raise ValueError(f"Cannot complete incident in status: {self.status}")

        self.status = IncidentStatus.COMPLETED
        self._touch()

    def fail(self) -> None:
        """Mark incident as failed."""
        self.status = IncidentStatus.FAILED
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
