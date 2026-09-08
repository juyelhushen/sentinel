from sentinel.agents.investigator.agent import InvestigatorAgent
from sentinel.workflows.graph_state import SentinelGraphState


def create_investigator_node(
        investigator_agent: InvestigatorAgent,
):
    """Create a LangGraph node that executes an investigation plan."""

    async def investigator_node(
            state: SentinelGraphState
    ) -> dict:
        """Execute the investigation plan."""

        try:
            plan = state["plan"]

            if plan is None:
                raise ValueError(
                    "Cannot investigate without a plan."
                )

            investigation = await investigator_agent.investigate(plan)

            return  {
                "investigation": investigation,
                "error": None
            }

        except Exception as exc:
            return {
                "investigation": None,
                "error": str(exc),
            }

    return investigator_node
