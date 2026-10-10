from dataclasses import dataclass, field
from uuid import UUID, uuid4

from sentinel.domain.models.verification import VerificationResult
from sentinel.domain.repair.approval import RepairApproval
from sentinel.domain.repair.models import RepairPlan


@dataclass(frozen=True)
class RepairAttempt:
    attempt_number: int
    repair_plan: RepairPlan
    verification: VerificationResult | None = None
    approval: RepairApproval | None = None
    execution_error: str | None = None
    id: UUID = field(default_factory=uuid4)
