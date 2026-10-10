from abc import ABC, abstractmethod

from sentinel.domain.repair.approval import RepairApproval
from sentinel.domain.repair.models import RepairPlan


class RepairApprovalGate(ABC):
    @abstractmethod
    async def approve(self, repair_plan: RepairPlan) -> RepairApproval:
        raise NotImplementedError