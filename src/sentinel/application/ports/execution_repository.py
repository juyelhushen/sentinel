from abc import ABC, abstractmethod
from uuid import UUID
from sentinel.domain.models.execution import Execution

class ExecutionRepository(ABC):
    """Persistence contract for executions."""

    @abstractmethod
    async def save(
            self,
            execution: Execution,
    ) -> None:
        """Persist an execution."""

    @abstractmethod
    async def get_by_id(
        self,
        execution_id: UUID,
    ) -> Execution | None:
        """Retrieve an execution by ID."""

    @abstractmethod
    async def get_by_incident_id(
        self,
        incident_id: UUID,
    ) -> list[Execution]:
        """Retrieve executions belonging to an incident."""