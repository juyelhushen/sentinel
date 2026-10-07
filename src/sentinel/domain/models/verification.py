from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4


class VerificationStatus(StrEnum):
    PASSED="passed"
    FAILED="failed"


@dataclass(frozen=True)
class VerificationResult:
    status: VerificationStatus
    summary: str
    test_output: str
    id: UUID = field(default_factory=uuid4)

    @property
    def passed(self) -> bool:
        return self.status == VerificationStatus.PASSED