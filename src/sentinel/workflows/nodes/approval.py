from collections.abc import Awaitable, Callable
from typing import Any

from sentinel.application.ports.repair_approval_gate import RepairApprovalGate
from sentinel.domain.repair.approval import (
    RepairApprovalStatus,
)
from sentinel.workflows.graph_state import SentinelGraphState


def create_repair_approval_node(
    approval_gate: RepairApprovalGate,
) -> Callable[[SentinelGraphState], Awaitable[dict[str, Any]]]:
    async def node(state: SentinelGraphState) -> dict[str, Any]:
        repair_plan = state.get("repair_plan")
        if repair_plan is None:
            raise ValueError("Cannot approve repair without a repair plan.")

        approval = await approval_gate.approve(repair_plan)
        error = None
        if approval.status == RepairApprovalStatus.REJECTED:
            error = approval.reason or "Repair approval was rejected."

        return {
            "approval": approval,
            "error": error,
            "verification": None,
        }

    return node
