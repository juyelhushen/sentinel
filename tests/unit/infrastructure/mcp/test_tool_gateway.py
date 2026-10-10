from unittest.mock import AsyncMock, Mock

import pytest

from sentinel.infrastructure.mcp.tool_gateway import MCPToolGateway
from sentinel.tools.models import ToolExecutionStatus, ToolRequest


@pytest.mark.asyncio
async def test_initialize_discovers_tools() -> None:
    client = AsyncMock()
    client.list_tools.return_value = (
        Mock(name="read_file"),
        Mock(name="search_code"),
    )
    client.tool_names = frozenset({"read_file", "search_code"})

    gateway = MCPToolGateway(client)

    await gateway.initialize()

    client.list_tools.assert_awaited_once()
    assert client.tool_names == frozenset({"read_file", "search_code"})


@pytest.mark.asyncio
async def test_execute_returns_failure_when_mcp_client_raises() -> None:

    client = Mock()
    client.tool_names = {"read_file"}
    client.call_tool = AsyncMock(side_effect=RuntimeError("connection lost"))

    gateway = MCPToolGateway(client)

    request = ToolRequest(
        tool_name="read_file",
        arguments={"path": "example.txt"},
    )

    result = await gateway.execute(request)

    assert result.status == ToolExecutionStatus.FAILURE
    assert result.error is not None
    assert "connection lost" in result.error
    assert result.request_id == request.request_id

    client.call_tool.assert_awaited_once_with(
        "read_file",
        {"path": "example.txt"},
    )