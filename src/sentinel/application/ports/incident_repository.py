from abc import ABC, abstractmethod
from collections.abc import Awaitable
from inspect import isawaitable
from uuid import UUID

from sentinel.domain.models.incident import Incident


class IncidentRepository(ABC):
    """Persistence contract for incidents."""

    @abstractmethod
    def save(self, incident: Incident) -> None | Awaitable[None]:
        """Persist an incident."""

    async def persist(self, incident: Incident) -> None:
        """Persist through synchronous or asynchronous adapters."""
        result = self.save(incident)
        if isawaitable(result):
            await result

    @abstractmethod
    def get(self, incident_id: UUID) -> Incident | None | Awaitable[Incident | None]:
        """Retrieve an incident by ID."""

    async def get_by_id(self, incident_id: UUID) -> Incident | None:
        """Retrieve through synchronous or asynchronous adapters."""
        result = self.get(incident_id)
        if isawaitable(result):
            return await result
        return result
