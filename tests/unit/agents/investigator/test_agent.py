from unittest.mock import AsyncMock

import pytest

from sentinel.agents.investigator.agent import InvestigatorAgent
from sentinel.agents.planner.models import InvestigationPlan, PlanStep, PlanStepType
from sentinel.application.ports.tool_gateway import ToolGateway
from sentinel.tools.models import ToolExecutionStatus, ToolResult


@pytest.mark.asyncio
async def test_investigator_agent_executes_plan() -> None:
    gateway = AsyncMock(spec=ToolGateway)

    gateway.execute.side_effect = [
        ToolResult(
            status=ToolExecutionStatus.SUCCESS,
            output="Tests passed",
        ),
        ToolResult(
            status=ToolExecutionStatus.SUCCESS,
            output="File contents found",
        ),
    ]

    investigator = InvestigatorAgent(
        tool_gateway=gateway,
    )

    plan = InvestigationPlan(
        summary="Investigate failing tests.",
        steps=(
            PlanStep(
                step_number=1,
                action=PlanStepType.RUN_TESTS,
                description="Run the tests",
            ),
            PlanStep(
                step_number=2,
                action=PlanStepType.INSPECT_FILE,
                description="Inspect the source file",
            ),
        ),
    )

    result = await investigator.investigate(plan)

    assert len(result.step_results) == 2

    assert result.step_results[0].success is True
    assert result.step_results[0].findings == "Tests passed."

    assert result.step_results[1].success is True
    assert result.step_results[1].findings == ("File contents found.")

    assert len(gateway.execute.call_args_list) == 2

    assert (
        gateway.execute.call_args_list[0].args[0].tool_name
        == "run_tests"
    )

    assert (
            gateway.execute.call_args_list[1].args[0].tool_name
            == "read_file"
    )

@pytest.mark.asyncio
async def test_investigator_agent_records_failed_tool() -> None:
    gateway = AsyncMock(spec=ToolGateway)

    gateway.execute.return_value = ToolResult(
        status=ToolExecutionStatus.FAILURE,
        error="Tests failed",
    )

    investigator = InvestigatorAgent(
        tool_gateway=gateway,
    )

    plan = InvestigationPlan(
        summary="Investigate failing tests.",
        steps=(
            PlanStep(
                step_number=1,
                action=PlanStepType.RUN_TESTS,
                description="Run the tests.",
            ),
        ),
    )

    result = await investigator.investigate(plan)

    assert len(result.step_results) == 1
    assert result.step_results[0].success is False
    assert result.step_results[0].findings == "Tests failed."


@pytest.mark.asyncio
async def test_investigator_agent_handles_empty_plan() -> None:
    gateway = AsyncMock(spec=ToolGateway)

    gateway.execute.side_effect = [
        ToolResult(
            status=ToolExecutionStatus.SUCCESS,
            output="Tests passed",
        ),
        ToolResult(
            status=ToolExecutionStatus.SUCCESS,
            output="File contents found",
        ),
    ]

    investigator = InvestigatorAgent(
        tool_gateway=gateway,
    )

    plan = InvestigationPlan(
        summary="Nothing to investigate.",
        steps=(),
    )

    result = await investigator.investigate(plan)

    assert result.step_results == ()
    assert result.summary == "No investigation steps were executed."

    assert gateway.execute.call_count == 0
