import pytest

from sentinel.agents.investigator.models import InvestigationResult
from sentinel.agents.planner.models import InvestigationPlan
from sentinel.domain.models.incident import Incident
from sentinel.workflows.sentinel_graph import create_sentinel_graph


class FakePlannerAgent:
    """Fake planner agents for graph tests"""

    async def plan(
            self,
            incident: Incident
    ) -> InvestigationPlan:

        return InvestigationPlan(
            summary=f"Plan for: {incident.title}",
            steps=(),
        )

class FakeInvestigatorAgent:
    """Fake investigator agents for graph tests"""

    async def investigate(
            self,
            plan: InvestigationPlan
    ) -> InvestigationResult:

        return InvestigationResult(
            summary=f"Investigated: {plan.summary}",
            step_results=(),
        )

@pytest.mark.asyncio
async def test_sentinel_graph_runs() -> None:
    graph = create_sentinel_graph(
        planner_agent=FakePlannerAgent(),
        investigator_agent=FakeInvestigatorAgent(),
    )

    incident = Incident(
        title="Tests are failing",
        description="Several tests are failing.",
        repository="sentinel",
    )

    result = await graph.ainvoke(
        {
            "incident": incident,
            'plan': None,
            "investigation": None,
            "error": None
        }
    )

    assert result["plan"].summary == ( "Plan for: Tests are failing" )
    assert result["error"] is None

class FailingPlannerAgent:
    """Planner agent that always fails."""

    async def plan(
            self,
            incident: Incident,
    ) -> InvestigationPlan:
        raise RuntimeError("LLM is unavailable")


@pytest.mark.asyncio
async def test_sentinel_graph_handles_planner_failure() -> None:
    graph = create_sentinel_graph(
        planner_agent=FailingPlannerAgent(),
        investigator_agent=FakeInvestigatorAgent(),
    )

    incident = Incident(
        title="Tests are failing",
        description="Several tests are failing.",
        repository="sentinel",
    )

    result = await graph.ainvoke(
        {
            "incident": incident,
            "plan": None,
            "error": None,
        }
    )

    assert result["plan"] is None
    assert result["error"] == "LLM is unavailable"