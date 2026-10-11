import pytest

from sentinel.agents.investigator.models import InvestigationResult
from sentinel.agents.planner.models import InvestigationPlan
from sentinel.domain.models.incident import Incident
from sentinel.workflows.nodes.investigator import create_investigator_node


class FakeInvestigatorAgent:
    """Fake investigator agent for graph tests."""

    async def investigate(
        self,
        plan: InvestigationPlan,
    ) -> InvestigationResult:

        return InvestigationResult(
            summary=f"Investigated: {plan.summary}",
            step_results=(),
        )


@pytest.mark.asyncio
async def test_investigator_node_adds_investigation() -> None:
    """Execute the investigator node."""

    investigator_node = create_investigator_node(
        investigator_agent=FakeInvestigatorAgent(),
    )

    incident = Incident(
        title="Test are failing",
        description="Several tests are failing",
        repository="sentinel",
    )

    plan = InvestigationPlan(
        summary="Investigate failing tests.",
        steps=(),
    )

    result = await investigator_node(
        {
            "incident": incident,
            "plan": plan,
            "investigation": None,
            "error": None,
        }
    )

    assert result["investigation"].summary == (
        "Investigated: Investigate failing tests."
    )

    assert result["error"] is None


@pytest.mark.asyncio
async def test_investigator_node_rejects_missing_plan() -> None:
    investigator_node = create_investigator_node(
        investigator_agent=FakeInvestigatorAgent(),
    )

    incident = Incident(
        title="Tests are failing",
        description="Several tests are failing.",
        repository="sentinel",
    )

    result = await investigator_node(
        {
            "incident": incident,
            "plan": None,
            "investigation": None,
            "error": None,
        }
    )

    assert result["investigation"] is None
    assert result["error"] == ("Cannot investigate without a plan.")


@pytest.mark.asyncio
async def test_investigator_node_captures_invalid_plan() -> None:
    class InvalidPlanAgent(FakeInvestigatorAgent):
        async def investigate(self, plan: InvestigationPlan) -> InvestigationResult:
            raise ValueError("No tool mapping exists for action")

    node = create_investigator_node(InvalidPlanAgent())

    result = await node({"plan": InvestigationPlan(summary="Investigate", steps=())})

    assert result == {
        "investigation": None,
        "error": "No tool mapping exists for action",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [TypeError, RuntimeError])
async def test_investigator_node_propagates_unexpected_errors(
    error_type: type[Exception],
) -> None:
    class BrokenInvestigatorAgent(FakeInvestigatorAgent):
        async def investigate(self, plan: InvestigationPlan) -> InvestigationResult:
            raise error_type("invalid investigator implementation")

    node = create_investigator_node(BrokenInvestigatorAgent())

    with pytest.raises(error_type, match="invalid investigator implementation"):
        await node({"plan": InvestigationPlan(summary="Investigate", steps=())})
