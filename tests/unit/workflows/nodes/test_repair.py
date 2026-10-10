from unittest.mock import AsyncMock

import pytest

from sentinel.agents.investigator.models import InvestigationResult
from sentinel.application.repair.repair_agent import RepairAgent
from sentinel.application.services.repair_execution_service import (
    RepairExecutionService,
)
from sentinel.domain.models.incident import Incident
from sentinel.domain.models.verification import VerificationResult, VerificationStatus
from sentinel.domain.repair.attempt import RepairAttempt
from sentinel.domain.repair.models import RepairPlan
from sentinel.tools.models import ToolExecutionStatus, ToolResult
from sentinel.workflows.graph_state import SentinelGraphState
from sentinel.workflows.nodes.repair import (
    record_repair_attempt_node,
    repair_node,
    repair_plan_node,
)


@pytest.fixture
def repair_plan() -> RepairPlan:
    return RepairPlan(summary="Fix null handling", steps=())


@pytest.mark.asyncio
@pytest.mark.parametrize("with_previous_attempt", [False, True])
async def test_repair_plan_node_reads_state(
    repair_plan: RepairPlan,
    with_previous_attempt: bool,
) -> None:
    agent = AsyncMock(spec=RepairAgent)
    agent.create_plan.return_value = repair_plan
    node = repair_plan_node(agent)
    assert callable(node)

    incident = Incident(
        title="Tests are failing",
        description="Null handling fails.",
        repository="sentinel",
    )
    investigation = InvestigationResult(summary="Missing null check", step_results=())
    state: SentinelGraphState = {
        "incident": incident,
        "investigation": investigation,
    }
    attempts = ()
    if with_previous_attempt:
        attempts = (RepairAttempt(attempt_number=1, repair_plan=repair_plan),)
        state["repair_attempts"] = attempts

    result = await node(state)

    agent.create_plan.assert_awaited_once_with(
        incident=incident,
        investigation=investigation,
        previous_attempts=attempts,
    )
    assert result == {"repair_plan": repair_plan}
    assert "repair_plan" not in state


@pytest.mark.asyncio
async def test_repair_plan_node_rejects_missing_investigation() -> None:
    agent = AsyncMock(spec=RepairAgent)
    incident = Incident(title="Failure", description="Failure", repository="sentinel")

    with pytest.raises(ValueError, match="without investigation"):
        await repair_plan_node(agent)({"incident": incident})

    agent.create_plan.assert_not_awaited()


@pytest.mark.asyncio
async def test_repair_plan_node_rejects_missing_incident() -> None:
    agent = AsyncMock(spec=RepairAgent)

    with pytest.raises(ValueError, match="without an incident"):
        await repair_plan_node(agent)({})

    agent.create_plan.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("results", "expected_error"),
    [
        ((ToolResult(status=ToolExecutionStatus.SUCCESS),), None),
        ((), "Repair was not executed."),
        (
            (
                ToolResult(status=ToolExecutionStatus.SUCCESS),
                ToolResult(status=ToolExecutionStatus.FAILURE, error="Approval denied"),
            ),
            "Approval denied",
        ),
        (
            (ToolResult(status=ToolExecutionStatus.FAILURE),),
            "Repair execution failed.",
        ),
    ],
)
async def test_repair_node_reads_plan_and_reports_execution_result(
    repair_plan: RepairPlan,
    results: tuple[ToolResult, ...],
    expected_error: str | None,
) -> None:
    service = AsyncMock(spec=RepairExecutionService)
    service.execute.return_value = results
    node = repair_node(service)
    assert callable(node)

    result = await node({"repair_plan": repair_plan})

    service.execute.assert_awaited_once_with(repair_plan)
    assert result == {"error": expected_error}


@pytest.mark.asyncio
async def test_repair_node_rejects_missing_plan() -> None:
    service = AsyncMock(spec=RepairExecutionService)

    with pytest.raises(ValueError, match="without a repair plan"):
        await repair_node(service)({})

    service.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("with_previous_attempt", [False, True])
async def test_record_repair_attempt_appends_without_mutating_state(
    repair_plan: RepairPlan,
    with_previous_attempt: bool,
) -> None:
    verification = VerificationResult(
        status=VerificationStatus.PASSED,
        summary="Tests passed",
        test_output="3 passed",
    )
    state: SentinelGraphState = {
        "repair_plan": repair_plan,
        "verification": verification,
    }
    attempts = ()
    if with_previous_attempt:
        attempts = (RepairAttempt(attempt_number=1, repair_plan=repair_plan),)
        state["repair_attempts"] = attempts

    result = await record_repair_attempt_node(state)

    assert set(result) == {"repair_attempts"}
    assert result["repair_attempts"][:-1] == attempts
    attempt = result["repair_attempts"][-1]
    assert isinstance(attempt, RepairAttempt)
    assert attempt.attempt_number == len(attempts) + 1
    assert attempt.repair_plan is repair_plan
    assert attempt.verification is verification
    assert state.get("repair_attempts", ()) == attempts


@pytest.mark.asyncio
async def test_record_repair_attempt_allows_skipped_verification(
    repair_plan: RepairPlan,
) -> None:
    result = await record_repair_attempt_node({"repair_plan": repair_plan})

    assert result["repair_attempts"][0].verification is None


@pytest.mark.asyncio
async def test_record_repair_attempt_rejects_missing_plan() -> None:
    with pytest.raises(ValueError, match="without repair plan"):
        await record_repair_attempt_node({})