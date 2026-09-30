from unittest.mock import AsyncMock

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


@pytest.mark.asyncio
async def test_executor_does_not_call_tool_when_policy_denies() -> None:
    registry = ToolRegistry()
    tool = FakeTool()
    registry.register(tool)

    policy = ToolPolicy(allowed_tools=set())

    executor = ToolExecutor(
        registry=registry,
        policy=policy,
    )

    # Policy denial must short-circuit before the underlying tool is ever invoked.
    tool.execute = AsyncMock()  # type: ignore[assignment]

    result = await executor.execute(
        ToolRequest(
            tool_name="fake_tool",
            arguments={},
        )
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert result.error == "Tool execution denied: fake_tool"
    tool.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_executor_returns_failure_for_unregistered_allowed_tool() -> None:
    registry = ToolRegistry()
    policy = ToolPolicy(allowed_tools={"fake_tool"})

    executor = ToolExecutor(
        registry=registry,
        policy=policy,
    )

    # Policy approval alone is not enough; registry membership remains required.
    result = await executor.execute(
        ToolRequest(
            tool_name="fake_tool",
            arguments={},
        )
    )

    assert result.status == ToolExecutionStatus.FAILURE
    assert "not registered" in result.error.lower()
