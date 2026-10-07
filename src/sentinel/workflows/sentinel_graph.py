from langgraph.constants import END, START
from langgraph.graph import StateGraph

from sentinel.agents.investigator.agent import InvestigatorAgent
from sentinel.agents.planner.agent import PlannerAgent
from sentinel.agents.verification.verification_agent import VerificationAgent
from sentinel.application.repair.repair_agent import RepairAgent
from sentinel.application.services.repair_execution_service import RepairExecutionService
from sentinel.domain.repair.retry import RepairRetryPolicy
from sentinel.workflows.graph_state import SentinelGraphState
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
):
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

    # ---------------------------------------------------------
    # 1. Execution lifecycle
    # ---------------------------------------------------------

    graph.add_node(
        "execution_start",
        execution_start_node,
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

        graph.add_node(
            "record_repair_attempt",
            record_repair_attempt_node,
        )

    # ---------------------------------------------------------
    # 7. Execution completion / failure
    # ---------------------------------------------------------

    graph.add_node(
        "execution_complete",
        execution_complete_node,
    )

    graph.add_node(
        "execution_fail",
        execution_fail_node,
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
            "repair",
        )

        graph.add_edge(
            "repair",
            "verification",
        )

        graph.add_edge(
            "verification",
            "record_repair_attempt",
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