from dataclasses import dataclass
from enum import StrEnum


class RepairApprovalStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class RepairApproval:
    status: RepairApprovalStatus
    reason: str = ""

    @property
    def approved(self) -> bool:
        return self.status == RepairApprovalStatus.APPROVED
