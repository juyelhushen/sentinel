import pytest

from sentinel.agents.investigator.agent import InvestigatorAgent
from sentinel.agents.planner.models import InvestigationPlan, PlanStep, PlanStepType
from sentinel.tools.models import ToolExecutionStatus, ToolResult


class FakeToolExecutor:
    """Fake tool executor for InvestigatorAgent tests."""

    def __init__(
            self,
            results: list[ToolResult],
    ) -> None:
        self._results = results
        self.requests: list[object] = []

    async def execute(self, request: object) -> ToolResult:
        self.requests.append(request)
        return self._results.pop(0)

@pytest.mark.asyncio
async def test_investigator_agent_executes_plan() -> None:
    executor = FakeToolExecutor(
        results=[
            ToolResult(
                status=ToolExecutionStatus.SUCCESS,
                output="Tests passed"
            ),
            ToolResult(
                status=ToolExecutionStatus.SUCCESS,
                output="File contents found"
            ),
        ]
    )

    agent = InvestigatorAgent(
        tool_executor=executor,
    )

    plan = InvestigationPlan(
        summary="Investigate failing tests.",
        steps=(
            PlanStep(
                step_number=1,
                action=PlanStepType.RUN_TESTS,
                description="Run the tests"
            ),
            PlanStep(
                step_number=2,
                action=PlanStepType.INSPECT_FILE,
                description="Inspect the source file"
            ),
        ),
    )

    result = await agent.investigate(plan)

    assert len(result.step_results) == 2

    assert result.step_results[0].success is True
    assert result.step_results[0].findings == "Tests passed."

    assert result.step_results[1].success is True
    assert result.step_results[1].findings == ( "File contents found." )

    assert len(executor.requests) == 2
    assert executor.requests[0].tool_name == "run_tests"
    assert executor.requests[1].tool_name == "read_file"

    
@pytest.mark.asyncio
async def test_investigator_agent_records_failed_tool() -> None:
    executor = FakeToolExecutor(
        results=[
            ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error="Tests failed.",
            ),
        ]
    )

    agent = InvestigatorAgent(
        tool_executor=executor,
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

    result = await agent.investigate(plan)
    assert len(result.step_results) == 1
    assert result.step_results[0].success is False
    assert result.step_results[0].findings == "Tests failed."


@pytest.mark.asyncio
async def test_investigator_agent_handles_empty_plan() -> None:
    executor = FakeToolExecutor(
        results=[]
    )

    agent = InvestigatorAgent(
        tool_executor=executor,
    )

    plan = InvestigationPlan(
        summary="Nothing to investigate.",
        steps=(),
    )

    result = await agent.investigate(plan)

    assert result.step_results == ()
    assert result.summary == (
        "No investigation steps were executed."
    )

    assert executor.requests == []