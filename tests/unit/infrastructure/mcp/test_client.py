from unittest.mock import AsyncMock

import pytest

from sentinel.infrastructure.mcp.client import SentinelMCPClient
from sentinel.infrastructure.mcp.models import MCPTool
from sentinel.infrastructure.mcp.tool_gateway import MCPToolGateway
from sentinel.tools.models import ToolExecutionStatus, ToolRequest


@pytest.mark.asyncio
async def test_mcp_client_discovers_and_builds_tool_cache():
    client = SentinelMCPClient()
    read_file = MCPTool(
        name="read_file",
        description="Read a UTF-8 text file from the repository.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file relative to the repository root.",
                },
            },
            "required": ["path"],
        },
    )
    search_code = MCPTool(
        name="search_code",
        description="Search repository source code for a text pattern.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["query"],
        },
    )
    run_tests = MCPTool(
        name="run_tests",
        description="Run a focused pytest target.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    )

    client._tools = {
        read_file.name: read_file,
        search_code.name: search_code,
        run_tests.name: run_tests,
    }

    assert client.tool_names == frozenset({
        "read_file",
        "search_code",
        "run_tests",
    })
    assert {tool.name for tool in client.tools} == {
        "read_file",
        "search_code",
        "run_tests",
    }
    assert client.get_tool("read_file") is read_file

    with pytest.raises(ValueError, match="MCP tool is not discovered"):
        client.get_tool("does_not_exist")


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
