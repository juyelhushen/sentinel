from unittest.mock import AsyncMock

import pytest

from sentinel.application.tools.local_gateway import LocalToolGateway
from sentinel.tools.models import ToolResult, ToolExecutionStatus, ToolRequest

@pytest.mark.asyncio
async def test_local_gateway_delegates_to_tool_executor():
    executor = AsyncMock()

    expected = ToolResult(
        status=ToolExecutionStatus.SUCCESS,
        output="file contents"
    )

    executor.execute.return_value = expected

    gateway = LocalToolGateway(executor)

    request = ToolRequest(
        tool_name="read_file",
        arguments={"path": "example.txt"},
    )

    result = await gateway.execute(request)
    assert result is expected
    executor.execute.assert_awaited_once_with(request)