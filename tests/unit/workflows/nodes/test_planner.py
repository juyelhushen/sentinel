import pytest

from sentinel.agents.planner.models import InvestigationPlan
from sentinel.agents.planner.parser import PlanParsingError
from sentinel.domain.models.incident import Incident
from sentinel.llm.exceptions import LLMConnectionError
from sentinel.workflows.nodes.planner import create_planner_node


class FakePlannerAgent:
    """Fake planner agent for workflow tests."""

    async def plan(
        self,
        incident: Incident,
    ) -> InvestigationPlan:

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
        raise LLMConnectionError(
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

    assert result["plan"].summary == ("Investigate: Tests are failing")
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

    result = await planner_node({"incident": incident, "plan": None, "error": None})

    assert result["plan"] is None
    assert result["error"] == "LLM is unavailable"


@pytest.mark.asyncio
async def test_planner_node_captures_parsing_error() -> None:
    class InvalidPlanAgent(FakePlannerAgent):
        async def plan(self, incident: Incident) -> InvestigationPlan:
            raise PlanParsingError("LLM response is not valid JSON.")

    node = create_planner_node(InvalidPlanAgent())
    incident = Incident(
        title="Failure", description="Tests failed", repository="sentinel"
    )

    result = await node({"incident": incident, "plan": None, "error": None})

    assert result == {"plan": None, "error": "LLM response is not valid JSON."}


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [TypeError, RuntimeError])
async def test_planner_node_propagates_unexpected_errors(
    error_type: type[Exception],
) -> None:
    class BrokenPlannerAgent(FakePlannerAgent):
        async def plan(self, incident: Incident) -> InvestigationPlan:
            raise error_type("invalid planner implementation")

    node = create_planner_node(BrokenPlannerAgent())
    incident = Incident(
        title="Failure", description="Tests failed", repository="sentinel"
    )

    with pytest.raises(error_type, match="invalid planner implementation"):
        await node({"incident": incident, "plan": None, "error": None})
