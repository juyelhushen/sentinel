from dataclasses import dataclass

from sentinel.application.ports.incident_repository import (
    IncidentRepository,
)
from sentinel.domain.models.incident import Incident


@dataclass(frozen=True)
class CreateIncidentCommand:
    """Input required to create an incident."""

    title: str
    description: str
    repository: str


class CreateIncidentUseCase:
    """Application use case for creating incidents."""

    def __init__(self, repository: IncidentRepository) -> None:
        self._repository = repository

    def execute(self, command: CreateIncidentCommand) -> Incident:
        """Create and persist an incident."""
        incident = Incident(
            title=command.title,
            description=command.description,
            repository=command.repository,
        )

        self._repository.save(incident)

        return incident