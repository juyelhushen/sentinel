
import pytest

from sentinel.application.services.repair_execution_service import (
    RepairExecutionService,
)
from sentinel.domain.repair import (
    RepairPlan,
    RepairStep,
    RepairStepType,
)
from sentinel.tools.models import ToolExecutionStatus, ToolResult


class FakeToolGateway:
    def __init__(
        self,
        results: tuple[ToolResult, ...],
    ) -> None:
        self.results = list(results)
        self.requests = []

    async def execute(self, request):
        self.requests.append(request)
        return self.results.pop(0)


def create_step(
    step_number: int,
    file_path: str,
) -> RepairStep:
    return RepairStep(
        step_number=step_number,
        action=RepairStepType.APPLY_PATCH,
        file_path=file_path,
        description=f"Fix step {step_number}",
        patch="--- a/file.py\n+++ b/file.py\n",
    )


@pytest.mark.asyncio
async def test_executes_repair_steps_in_order() -> None:
    gateway = FakeToolGateway(
        results=(
            ToolResult(
                status=ToolExecutionStatus.SUCCESS,
                output="Step 1 applied.",
            ),
            ToolResult(
                status=ToolExecutionStatus.SUCCESS,
                output="Step 2 applied.",
            ),
        )
    )

    plan = RepairPlan(
        summary="Fix issue",
        steps=(
            create_step(1, "src/service.py"),
            create_step(2, "src/repository.py"),
        ),
    )

    service = RepairExecutionService(
        tool_gateway=gateway,
    )

    results = await service.execute(plan)

    assert len(results) == 2
    assert all(result.succeeded for result in results)

    assert len(gateway.requests) == 2

    assert gateway.requests[0].tool_name == "apply_patch"
    assert gateway.requests[0].arguments["file_path"] == "src/service.py"

    assert gateway.requests[1].tool_name == "apply_patch"
    assert gateway.requests[1].arguments["file_path"] == "src/repository.py"


@pytest.mark.asyncio
async def test_stops_after_first_failed_step() -> None:
    gateway = FakeToolGateway(
        results=(
            ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error="Patch context does not match.",
            ),
            ToolResult(
                status=ToolExecutionStatus.SUCCESS,
                output="Should not execute.",
            ),
        )
    )

    plan = RepairPlan(
        summary="Fix issue",
        steps=(
            create_step(1, "src/service.py"),
            create_step(2, "src/repository.py"),
        ),
    )

    service = RepairExecutionService(
        tool_gateway=gateway,
    )

    results = await service.execute(plan)

    assert len(results) == 1
    assert not results[0].succeeded

    assert len(gateway.requests) == 1
    assert gateway.requests[0].arguments["file_path"] == "src/service.py"


@pytest.mark.asyncio
async def test_empty_repair_plan_returns_no_results() -> None:
    gateway = FakeToolGateway(results=())

    plan = RepairPlan(
        summary="No safe repair identified.",
        steps=(),
    )

    service = RepairExecutionService(
        tool_gateway=gateway,
    )

    results = await service.execute(plan)

    assert results == ()
    assert gateway.requests == []