from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from sentinel.infrastructure.mcp.tool_gateway import MCPToolGateway
from sentinel.tools.models import ToolRequest, ToolExecutionStatus


@pytest.mark.asyncio
async def test_mcp_gateway_returns_successful_tool_result():
    client = AsyncMock()

    client.call_tool.return_value = SimpleNamespace(
        is_error=False,
        content=[
            SimpleNamespace(text="file contents"),
        ],
    )

    gateway = MCPToolGateway(client)

    request = ToolRequest(
        tool_name="read_file",
        arguments={"path": "example.txt"},
    )

    result = await gateway.execute(request)

    assert result.status == ToolExecutionStatus.SUCCESS
    assert result.output == "file contents"
    assert result.request_id == request.request_id

    client.call_tool.assert_awaited_once_with(
        "read_file",
        {"path": "example.txt"},
    )

@pytest.mark.asyncio
async def test_mcp_gateway_translates_mcp_error():
    client = AsyncMock()

    client.call_tool.return_value = SimpleNamespace(
        is_error=True,
        content=[
            SimpleNamespace(text="File not found"),
        ],
    )

    gateway = MCPToolGateway(client)

    request = ToolRequest(
        tool_name="read_file",
        arguments={"path": "missing.txt"},
    )

    result = await gateway.execute(request)

    assert result.status == ToolExecutionStatus.FAILURE
    assert result.error == "File not found"
    assert result.request_id == request.request_id
    
@pytest.mark.asyncio
async def test_mcp_gateway_combines_text_content():
    client = AsyncMock()

    client.call_tool.return_value = SimpleNamespace(
        is_error=False,
        content=[
            SimpleNamespace(text="line 1"),
            SimpleNamespace(text="line 2"),
        ],
    )

    gateway = MCPToolGateway(client)

    request = ToolRequest(
        tool_name="read_file",
        arguments={"path": "example.txt"},
    )

    result = await gateway.execute(request)

    assert result.output == "line 1\nline 2"