import pytest

from sentinel.agents.investigator.models import InvestigationResult
from sentinel.application.repair.repair_agent import RepairAgent
from sentinel.domain.models.incident import Incident
from sentinel.domain.models.verification import VerificationResult, VerificationStatus
from sentinel.domain.repair.attempt import RepairAttempt
from sentinel.domain.repair.models import RepairPlan, RepairStep, RepairStepType
from tests.unit.application.agents.test_repair_agent import FakeLLMProvider


@pytest.mark.asyncio
async def test_repair_agent_accepts_previous_attempts() -> None:
    incident = Incident(
        title="Null pointer error",
        description="Order creation fails when customer is missing.",
        repository="test-repository",
    )

    investigation = InvestigationResult(
        summary="customer.id is accessed without a null check.",
        step_results=(),
    )

    previous_plan = RepairPlan(
        summary="First repair attempt",
        steps=(
            RepairStep(
                step_number=1,
                action=RepairStepType.APPLY_PATCH,
                file_path="src/service.py",
                description="Add null check",
                patch="patch",
            ),
        ),
    )

    previous_verification = VerificationResult(
        status=VerificationStatus.FAILED,
        summary="Verification tests failed.",
        test_output="1 failed, 2 passed",
    )

    previous_attempt = RepairAttempt(
        attempt_number=1,
        repair_plan=previous_plan,
        verification=previous_verification,
    )

    agent = RepairAgent(
        llm_provider=FakeLLMProvider(),
    )

    plan = await agent.create_plan(
        incident=incident,
        investigation=investigation,
        previous_attempts=(previous_attempt,),
    )

    assert plan.summary == "Fix null handling"