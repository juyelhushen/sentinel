from langgraph.constants import START, END
from langgraph.graph import StateGraph

from sentinel.agents.investigator.agent import InvestigatorAgent
from sentinel.agents.planner.agent import PlannerAgent
from sentinel.workflows.graph_state import SentinelGraphState
from sentinel.workflows.nodes.error import error_node
from sentinel.workflows.nodes.investigator import create_investigator_node
from sentinel.workflows.nodes.planner import create_planner_node
from sentinel.workflows.routing import route_after_planning


def create_sentinel_graph(
        planner_agent: PlannerAgent,
        investigator_agent: InvestigatorAgent,
):
    """Create Sentinel's LangGraph workflow."""

    graph = StateGraph(
        SentinelGraphState
    )

    graph.add_node(
        "planner",
        create_planner_node(planner_agent),
    )

    graph.add_node(
        "investigator",
        create_investigator_node(investigator_agent)
    )

    graph.add_node(
        "error",
        error_node
    )

    graph.add_edge(
        START,
        "planner",
    )

    graph.add_conditional_edges(
        "planner",
        route_after_planning,
        {
            "investigator": "investigator",
            "error": "error"
        },
    )

    graph.add_edge(
        "investigator",
        END,
    )

    graph.add_edge(
        "error",
        END
    )

    return graph.compile()