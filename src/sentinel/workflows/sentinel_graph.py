from typing import Any, cast

from langgraph.constants import END, START
from langgraph.graph import StateGraph

from sentinel.agents.investigator.agent import InvestigatorAgent
from sentinel.agents.planner.agent import PlannerAgent
from sentinel.agents.verification.verification_agent import VerificationAgent
from sentinel.application.ports.execution_repository import ExecutionRepository
from sentinel.application.ports.incident_repository import IncidentRepository
from sentinel.application.ports.repair_approval_gate import RepairApprovalGate
from sentinel.application.ports.repair_repository import RepairRepository
from sentinel.application.repair.repair_agent import RepairAgent
from sentinel.application.services.repair_execution_service import (
    RepairExecutionService,
)
from sentinel.domain.repair.approval import RepairApproval, RepairApprovalStatus
from sentinel.domain.repair.models import RepairPlan
from sentinel.domain.repair.retry import RepairRetryPolicy
from sentinel.workflows.graph_state import SentinelGraphState
from sentinel.workflows.nodes.approval import create_repair_approval_node
from sentinel.workflows.nodes.complete_execution import execution_complete_node
from sentinel.workflows.nodes.execution import execution_start_node
from sentinel.workflows.nodes.fail_execution import execution_fail_node
from sentinel.workflows.nodes.investigator import create_investigator_node
from sentinel.workflows.nodes.planner import create_planner_node
from sentinel.workflows.nodes.repair import (
    record_repair_attempt_node,
    repair_node,
    repair_plan_node,
)
from sentinel.workflows.nodes.verification import (
    create_verification_router,
    verification_node,
)
from sentinel.workflows.routing import route_after_planning


def create_sentinel_graph(
    planner_agent: PlannerAgent,
    investigator_agent: InvestigatorAgent,
    repair_agent: RepairAgent | None = None,
    repair_execution_service: RepairExecutionService | None = None,
    verification_agent: VerificationAgent | None = None,
    verification_path: str = "tests",
    retry_policy: RepairRetryPolicy | None = None,
    approval_gate: RepairApprovalGate | None = None,
    repair_repository: RepairRepository | None = None,
    incident_repository: IncidentRepository | None = None,
    execution_repository: ExecutionRepository | None = None,
) -> Any:
    """Create Sentinel's LangGraph workflow."""

    repair_enabled = any(
        dependency is not None
        for dependency in (
            repair_agent,
            repair_execution_service,
            verification_agent,
        )
    )
    if repair_enabled and (
        repair_agent is None
        or repair_execution_service is None
        or verification_agent is None
    ):
        raise ValueError(
            "Repair workflow requires a repair agent, repair execution service, "
            "and verification agent."
        )

    graph = StateGraph(SentinelGraphState)

    async def start_execution(state: SentinelGraphState) -> dict[str, Any]:
        update = execution_start_node(state)
        incident = state.get("incident")
        if incident_repository is not None and incident is not None:
            await incident_repository.persist(incident)
        if execution_repository is not None:
            await execution_repository.save(update["execution"])
        update["repair_enabled"] = repair_enabled
        return update

    async def complete_execution(state: SentinelGraphState) -> dict[str, Any]:
        update = execution_complete_node(state)
        incident = state.get("incident")
        if incident_repository is not None and incident is not None:
            await incident_repository.persist(incident)
        if execution_repository is not None:
            await execution_repository.save(update["execution"])
        return update

    async def fail_execution(state: SentinelGraphState) -> dict[str, Any]:
        update = execution_fail_node(state)
        incident = state.get("incident")
        if incident_repository is not None and incident is not None:
            await incident_repository.persist(incident)
        execution = update.get("execution")
        if execution is not None and execution_repository is not None:
            await execution_repository.save(execution)
        return update

    # ---------------------------------------------------------
    # 1. Execution lifecycle
    # ---------------------------------------------------------

    graph.add_node(
        "execution_start",
        start_execution,
    )

    # ---------------------------------------------------------
    # 2. Investigation
    # ---------------------------------------------------------

    graph.add_node(
        "planner",
        create_planner_node(planner_agent),
    )

    graph.add_node(
        "investigator",
        create_investigator_node(investigator_agent),
    )

    # ---------------------------------------------------------
    # 3. Repair planning
    # ---------------------------------------------------------

    if (
        repair_agent is not None
        and repair_execution_service is not None
        and verification_agent is not None
    ):
        graph.add_node(
            "repair_plan",
            repair_plan_node(repair_agent),
        )

        if approval_gate is None:

            class AutoApproveGate(RepairApprovalGate):
                async def approve(self, repair_plan: RepairPlan) -> RepairApproval:
                    return RepairApproval(RepairApprovalStatus.APPROVED)

            effective_approval_gate: RepairApprovalGate = AutoApproveGate()
        else:
            effective_approval_gate = approval_gate

        graph.add_node(
            "repair_approval",
            cast(Any, create_repair_approval_node(effective_approval_gate)),
        )

        async def record_repair_attempt(
            state: SentinelGraphState,
        ) -> dict[str, Any]:
            return await record_repair_attempt_node(state, repair_repository)

        graph.add_node("record_repair_attempt", record_repair_attempt)

        # ---------------------------------------------------------
        # 4. Repair execution
        # ---------------------------------------------------------

        graph.add_node(
            "repair",
            repair_node(
                repair_execution_service,
            ),
        )

        # ---------------------------------------------------------
        # 5. Verification
        # ---------------------------------------------------------

        graph.add_node(
            "verification",
            verification_node(
                verification_agent,
                verification_path,
            ),
        )

    # ---------------------------------------------------------
    # 6. Record repair attempt
    # ---------------------------------------------------------

    # ---------------------------------------------------------
    # 7. Execution completion / failure
    # ---------------------------------------------------------

    graph.add_node(
        "execution_complete",
        complete_execution,
    )

    graph.add_node(
        "execution_fail",
        fail_execution,
    )

    # ---------------------------------------------------------
    # 8. Linear workflow
    # ---------------------------------------------------------

    graph.add_edge(
        START,
        "execution_start",
    )

    graph.add_edge(
        "execution_start",
        "planner",
    )

    graph.add_conditional_edges(
        "planner",
        route_after_planning,
        {
            "investigator": "investigator",
            "fail_execution": "execution_fail",
        },
    )

    def route_after_investigation(state: SentinelGraphState) -> str:
        if state.get("error") is not None:
            return "execution_fail"

        return "repair_plan" if repair_enabled else "execution_complete"

    graph.add_conditional_edges(
        "investigator",
        route_after_investigation,
        {
            "execution_fail": "execution_fail",
            "repair_plan" if repair_enabled else "execution_complete": (
                "repair_plan" if repair_enabled else "execution_complete"
            ),
        },
    )

    if repair_enabled:
        graph.add_edge(
            "repair_plan",
            "repair_approval",
        )

        def route_after_approval(state: SentinelGraphState) -> str:
            if state.get("error") is not None:
                return "rejected"
            return "approved"

        graph.add_conditional_edges(
            "repair_approval",
            route_after_approval,
            {
                "approved": "repair",
                "rejected": "record_repair_attempt",
            },
        )

        # ---------------------------------------------------------
        # 9. Verification decision / retry loop
        # ---------------------------------------------------------

        graph.add_conditional_edges(
            "record_repair_attempt",
            create_verification_router(
                retry_policy if retry_policy is not None else RepairRetryPolicy(),
            ),
            {
                "complete": "execution_complete",
                "retry": "repair_plan",
                "failure": "execution_fail",
            },
        )

        graph.add_conditional_edges(
            "repair",
            lambda state: "verify" if state.get("error") is None else "record",
            {
                "verify": "verification",
                "record": "record_repair_attempt",
            },
        )

        graph.add_edge(
            "verification",
            "record_repair_attempt",
        )

    # ---------------------------------------------------------
    # 10. Terminal states
    # ---------------------------------------------------------

    graph.add_edge(
        "execution_complete",
        END,
    )

    graph.add_edge(
        "execution_fail",
        END,
    )

    return graph.compile()
