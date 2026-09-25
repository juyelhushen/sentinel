from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from sentinel.infrastructure.mcp.server import SentinelMCPServer


@pytest.mark.asyncio
async def test_read_file_tool_delegates_to_tool_executor():
    tool_executor = AsyncMock()

    result = type(
        "ToolResultStub",
        (),
        {
            "succeeded": True,
            "output": "file contents",
            "error": None,
        },
    )()

    tool_executor.return_value = result

    mcp_server = SentinelMCPServer(
        repository_root=Path("."),
        tool_executor=tool_executor,
    )

    tools = await mcp_server.server.list_tools()

    assert any(tool.name == "read_file" for tool in tools)


