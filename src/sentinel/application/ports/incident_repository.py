from abc import ABC, abstractmethod
from uuid import UUID

from sentinel.domain.models.incident import Incident


class IncidentRepository(ABC):
    """Port for incident persistence."""

    @abstractmethod
    def save(self, incident: Incident) -> None:
        """Persist an incident."""

    @abstractmethod
    def get(self, incident_id: UUID) -> Incident | None:
        """Retrieve an incident by ID."""