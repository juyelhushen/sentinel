import pytest

from unittest.mock import AsyncMock

from sentinel.infrastructure.mcp.tool_gateway import MCPToolGateway
from sentinel.tools.models import ToolRequest, ToolExecutionStatus


@pytest.mark.asyncio
async def test_mcp_gateway_rejects_unknown_tool():
    client = AsyncMock()

    client.tool_names = frozenset(
        {
            "read_file",
            "search_code",
            "run_tests",
        }
    )

    gateway = MCPToolGateway(client)

    request = ToolRequest(
        tool_name="delete_repository",
        arguments={},
    )

    result = await gateway.execute(request)

    assert result.status == ToolExecutionStatus.FAILURE
    assert "not available" in (result.error or "")

    client.call_tool.assert_not_awaited()
