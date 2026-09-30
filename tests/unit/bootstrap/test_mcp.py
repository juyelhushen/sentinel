from unittest.mock import AsyncMock, patch

import pytest

from sentinel.bootstrap.mcp import create_mcp_tool_gateway
from sentinel.infrastructure.mcp.tool_gateway import MCPToolGateway


@pytest.mark.asyncio
async def test_create_mcp_tool_gateway_connects_client():
    with patch("sentinel.bootstrap.mcp.SentinelMCPClient") as client_class:
        client = client_class.return_value
        client.connect = AsyncMock()
        client.list_tools = AsyncMock(
            return_value=(
                type(
                    "ToolStub",
                    (),
                    {"name": "read_file"},
                )(),
                type(
                    "ToolStub",
                    (),
                    {"name": "search_code"},
                )(),
                type(
                    "ToolStub",
                    (),
                    {"name": "run_tests"},
                )(),
            )
        )

        result_client, gateway = await create_mcp_tool_gateway(
            command="uv",
            args=[
                "run",
                "python",
                "-m",
                "sentinel.infrastructure.mcp.stdio_server",
            ],
        )

        assert result_client is client
        assert isinstance(gateway, MCPToolGateway)

        client.connect.assert_awaited_once_with(
            command="uv",
            args=[
                "run",
                "python",
                "-m",
                "sentinel.infrastructure.mcp.stdio_server",
            ],
        )

        client.list_tools.assert_awaited_once()
