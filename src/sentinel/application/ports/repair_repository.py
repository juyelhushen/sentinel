from abc import ABC, abstractmethod
from uuid import UUID

from sentinel.domain.repair.attempt import RepairAttempt


class RepairRepository(ABC):
    
    @abstractmethod
    async def save_attempt(
        self,
        execution_id: UUID,
        attempt: RepairAttempt,
    ) -> None:
        raise NotImplementedError
    
    @abstractmethod
    async def get_attempts(
        self,
        execution_id: UUID,
    ) -> list[RepairAttempt]:
        raise NotImplementedError