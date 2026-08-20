import pytest

from sentinel.tools.executor import ToolExecutor
from sentinel.tools.models import (
    ToolExecutionStatus,
    ToolRequest,
    ToolResult,
)
from sentinel.tools.policy import ToolPolicy
from sentinel.tools.registry import ToolRegistry


class FakeTool:
    name = "fake_tool"
    description = "Fake tool."

    async def execute(self, request: ToolRequest) -> ToolResult:
        return ToolResult(
            status=ToolExecutionStatus.SUCCESS,
            output="success",
            request_id=request.request_id,
        )


@pytest.mark.asyncio
async def test_executor_runs_allowed_tool() -> None:
    registry = ToolRegistry()
    registry.register(FakeTool())

    policy = ToolPolicy(allowed_tools={"fake_tool"})

    executor = ToolExecutor(
        registry=registry,
        policy=policy,
    )

    result = await executor.execute(
        ToolRequest(
            tool_name="fake_tool",
            arguments={},
        )
    )

    assert result.status == ToolExecutionStatus.SUCCESS
    assert result.output == "success"


@pytest.mark.asyncio
async def test_executor_denies_disallowed_tool() -> None:
    registry = ToolRegistry()
    registry.register(FakeTool())

    policy = ToolPolicy(allowed_tools=set())

    executor = ToolExecutor(
        registry=registry,
        policy=policy,
    )

    result = await executor.execute(
        ToolRequest(
            tool_name="fake_tool",
            arguments={},
        )
    )

    assert result.status == ToolExecutionStatus.DENIED
