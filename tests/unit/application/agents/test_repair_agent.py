import pytest

from sentinel.agents.investigator.models import (
    InvestigationResult,
    StepInvestigationResult,
)
from sentinel.agents.planner.models import PlanStepType
from sentinel.application.repair.repair_agent import RepairAgent
from sentinel.domain.models.incident import Incident


class FakeLLMProvider:
    async def generate(self, request):
        class Response:
            content = """
            {
              "summary": "Fix null handling",
              "steps": [
                {
                  "step_number": 1,
                  "action": "apply_patch",
                  "file_path": "src/service.py",
                  "description": "Add null check",
                  "patch": "--- a/src/service.py\\n+++ b/src/service.py"
                }
              ]
            }
            """

        return Response()


@pytest.mark.asyncio
async def test_repair_agent_creates_plan() -> None:
    incident = Incident(
        title="Null pointer error",
        description="Order creation fails when customer is missing.",
        repository="test-repository",
    )

    investigation = InvestigationResult(
        summary="Customer can be missing before customer.id is accessed.",
        step_results=(
            StepInvestigationResult(
                step_number=1,
                action=PlanStepType.INSPECT_FILE,
                success=True,
                findings="customer.id is accessed without a null check.",
            ),
        ),
    )

    agent = RepairAgent(
        llm_provider=FakeLLMProvider(),
    )

    plan = await agent.create_plan(
        incident=incident,
        investigation=investigation,
    )

    assert plan.summary == "Fix null handling"
    assert len(plan.steps) == 1
    assert plan.steps[0].file_path == "src/service.py"