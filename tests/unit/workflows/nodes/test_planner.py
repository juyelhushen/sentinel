import pytest

from sentinel.agents.planner.models import InvestigationPlan
from sentinel.domain.models import incident
from sentinel.domain.models.incident import Incident
from sentinel.workflows.nodes.planner import create_planner_node


class FakePlannerAgent:
    """Fake planner agent for workflow tests."""

    async def plan(
            self,
            incident: Incident,
    )-> InvestigationPlan:

        return InvestigationPlan(
            summary=f"Investigate: {incident.title}",
            steps=(),
        )

class FailingPlannerAgent:
    """Planner agent that always fails"""
    async def plan(
            self,
            incident: Incident,
    ):
        raise RuntimeError(
            "LLM is unavailable",
        )

@pytest.mark.asyncio
async def test_planner_node_adds_plan_to_state() -> None:
    planner_agent = FakePlannerAgent()
    planner_node = create_planner_node(
        planner_agent=planner_agent,
    )

    incident = Incident(
        title="Tests are failing",
        description="Several tests are failing.",
        repository="sentinel",
    )

    result = await planner_node(
        {
            "incident": incident,
            "plan": None,
            "error": None,
        }
    )

    assert result["plan"].summary == ( "Investigate: Tests are failing" )
    assert result["error"] is None

@pytest.mark.asyncio
async def test_planner_node_captures_error() -> None:
    planner_node = create_planner_node(
        planner_agent=FailingPlannerAgent(),
    )

    incident = Incident(
        title="Tests are failing",
        description="Several tests are failing.",
        repository="sentinel",
    )

    result = await planner_node(
        {
            "incident": incident,
            "plan": None,
            "error": None
        }
    )

    assert result["plan"] is None
    assert result["error"] == "LLM is unavailable"