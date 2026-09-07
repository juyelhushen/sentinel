from sentinel.agents.planner.agent import PlannerAgent
from sentinel.workflows.graph_state import SentinelGraphState


def create_planner_node(planner_agent: PlannerAgent):
    """Create a LangGraph node that generates an investigation plan."""

    async def planner_node(state: SentinelGraphState) -> dict:
        """Generate an investigation plan."""

        try:
            plan = await planner_agent.plan(
                state["incident"]
            )

            return {
                "plan": plan,
                "error": None
            }
        except Exception as exc:
            return {
                "plan": None,
                "error": str(exc)
            }

    return planner_node
