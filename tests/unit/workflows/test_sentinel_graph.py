from unittest.mock import AsyncMock

import pytest

from sentinel.agents.investigator.models import InvestigationResult
from sentinel.agents.planner.models import InvestigationPlan
from sentinel.agents.verification.verification_agent import VerificationAgent
from sentinel.application.repair.repair_agent import RepairAgent
from sentinel.application.services.repair_execution_service import (
    RepairExecutionService,
)
from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.models.incident import Incident
from sentinel.domain.models.verification import VerificationResult, VerificationStatus
from sentinel.domain.repair.models import RepairPlan
from sentinel.domain.repair.retry import RepairRetryPolicy
from sentinel.tools.models import ToolExecutionStatus, ToolResult
from sentinel.workflows.sentinel_graph import create_sentinel_graph


class FakePlannerAgent:
    """Fake planner agents for graph tests"""

    async def plan(self, incident: Incident) -> InvestigationPlan:

        return InvestigationPlan(
            summary=f"Plan for: {incident.title}",
            steps=(),
        )


class FakeInvestigatorAgent:
    """Fake investigator agents for graph tests"""

    async def investigate(self, plan: InvestigationPlan) -> InvestigationResult:

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
        {"incident": incident, "plan": None, "investigation": None, "error": None}
    )

    assert result["plan"].summary == ("Plan for: Tests are failing")
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
            "investigation": None,
            "error": None,
        }
    )

    assert result["plan"] is None
    assert result["error"] == "LLM is unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("statuses", "max_attempts", "expected_status"),
    [
        ([VerificationStatus.PASSED], 3, ExecutionStatus.COMPLETED),
        (
            [VerificationStatus.FAILED, VerificationStatus.PASSED],
            3,
            ExecutionStatus.COMPLETED,
        ),
        (
            [VerificationStatus.FAILED, VerificationStatus.FAILED],
            2,
            ExecutionStatus.FAILED,
        ),
    ],
)
async def test_sentinel_graph_runs_repair_nodes_with_langgraph_state(
    statuses: list[VerificationStatus],
    max_attempts: int,
    expected_status: ExecutionStatus,
) -> None:
    repair_agent = AsyncMock(spec=RepairAgent)
    repair_plan = RepairPlan(summary="Fix null handling", steps=())
    repair_agent.create_plan.return_value = repair_plan
    service = AsyncMock(spec=RepairExecutionService)
    service.execute.return_value = (ToolResult(status=ToolExecutionStatus.SUCCESS),)
    verification_agent = AsyncMock(spec=VerificationAgent)
    verifications = [
        VerificationResult(status=status, summary="Tests finished", test_output="output")
        for status in statuses
    ]
    verification_agent.verify.side_effect = verifications
    graph = create_sentinel_graph(
        planner_agent=FakePlannerAgent(),
        investigator_agent=FakeInvestigatorAgent(),
        repair_agent=repair_agent,
        repair_execution_service=service,
        verification_agent=verification_agent,
        verification_path="tests/test_order.py",
        retry_policy=RepairRetryPolicy(max_attempts=max_attempts),
    )
    incident = Incident(title="Failure", description="Null handling", repository="sentinel")

    result = await graph.ainvoke({"incident": incident})

    attempts = result["repair_attempts"]
    assert len(attempts) == len(statuses)
    assert result["execution"].status == expected_status
    assert result["verification"] is verifications[-1]
    assert result["error"] is None
    assert service.execute.await_count == len(statuses)
    assert verification_agent.verify.await_count == len(statuses)
    for index, call in enumerate(repair_agent.create_plan.await_args_list):
        assert call.kwargs["incident"] is incident
        assert call.kwargs["investigation"] is result["investigation"]
        assert call.kwargs["previous_attempts"] == attempts[:index]
        assert attempts[index].attempt_number == index + 1
        assert attempts[index].repair_plan is repair_plan
        assert attempts[index].verification is verifications[index]
    for call in service.execute.await_args_list:
        assert call.args == (repair_plan,)
    for call in verification_agent.verify.await_args_list:
        assert call.kwargs == {"test_path": "tests/test_order.py"}


@pytest.mark.asyncio
async def test_sentinel_graph_skips_verification_after_repair_failure() -> None:
    repair_agent = AsyncMock(spec=RepairAgent)
    repair_agent.create_plan.return_value = RepairPlan(summary="Repair", steps=())
    service = AsyncMock(spec=RepairExecutionService)
    service.execute.return_value = (
        ToolResult(status=ToolExecutionStatus.FAILURE, error="Approval denied"),
    )
    verification_agent = AsyncMock(spec=VerificationAgent)
    graph = create_sentinel_graph(
        planner_agent=FakePlannerAgent(),
        investigator_agent=FakeInvestigatorAgent(),
        repair_agent=repair_agent,
        repair_execution_service=service,
        verification_agent=verification_agent,
    )
    incident = Incident(title="Failure", description="Failure", repository="sentinel")

    result = await graph.ainvoke({"incident": incident})

    verification_agent.verify.assert_not_awaited()
    assert result["error"] == "Approval denied"
    assert result["execution"].status == ExecutionStatus.FAILED
    assert result["verification"] is None
    assert len(result["repair_attempts"]) == 1
    assert result["repair_attempts"][0].verification is None


def test_sentinel_graph_rejects_partial_repair_dependencies() -> None:
    with pytest.raises(ValueError, match="Repair workflow requires"):
        create_sentinel_graph(
            planner_agent=FakePlannerAgent(),
            investigator_agent=FakeInvestigatorAgent(),
            repair_agent=AsyncMock(spec=RepairAgent),
        )
