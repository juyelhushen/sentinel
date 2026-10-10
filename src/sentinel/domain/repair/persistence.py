from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class PersistedRepairAttempt:
    execution_id:UUID
    attempt_number: int
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    
    
