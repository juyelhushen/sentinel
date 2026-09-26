from pathlib import Path

import pytest

from sentinel.infrastructure.mcp.client import SentinelMCPClient


@pytest.mark.asyncio
async def test_mcp_client_can_discover_and_call_read_file():
    repository_root = Path(__file__).resolve().parents[3]

    client = SentinelMCPClient()

    try:
        await client.connect(
            command="uv",
            args=[
                "run",
                "python",
                "-m",
                "sentinel.infrastructure.mcp.stdio_server",
            ],
            env={
                "SENTINEL_REPOSITORY_ROOT": str(repository_root),
            },
        )

        tools = await client.list_tools()

        tool_names = {tool.name for tool in tools}

        assert "read_file" in tool_names

        result = await client.call_tool(
            "read_file",
            {
                "path": "tests/fixtures/mcp/example.txt",
            },
        )

        assert result.is_error is False

        text = "\n".join(
            item.text
            for item in result.content
            if hasattr(item, "text")
        )

        assert "Hello from Sentinel MCP!" in text



    finally:
        await client.close()

@pytest.mark.asyncio
async def test_mcp_read_file_returns_error_for_missing_file():
    client = SentinelMCPClient()

    try:
        await client.connect(
            command="uv",
            args=[
                "run",
                "python",
                "-m",
                "sentinel.infrastructure.mcp.stdio_server",
            ],
        )

        result = await client.call_tool(
            "read_file",
            {
                "path": "tests/fixtures/mcp/does-not-exist.txt",
            },
        )

        assert result.is_error is True

    finally:
        await client.close()

@pytest.mark.asyncio
async def test_mcp_read_file_rejects_path_traversal():
    client = SentinelMCPClient()

    try:
        await client.connect(
            command="uv",
            args=[
                "run",
                "python",
                "-m",
                "sentinel.infrastructure.mcp.stdio_server",
            ],
        )

        result = await client.call_tool(
            "read_file",
            {
                "path": "../../outside.txt",
            },
        )

        assert result.is_error is True

    finally:
        await client.close()


@pytest.mark.asyncio
async def test_mcp_client_can_call_search_code():
    client = SentinelMCPClient()

    try:
        await client.connect(
            command="uv",
            args=[
                "run",
                "python",
                "-m",
                "sentinel.infrastructure.mcp.stdio_server",
            ],
        )

        result = await client.call_tool(
            "search_code",
            {
                "query": "Hello from Sentinel MCP!",
                "path": "tests/fixtures/mcp",
            },
        )

        assert result.is_error is False
        assert result.content

        text = "\n".join(
            item.text
            for item in result.content
            if hasattr(item, "text")
        )

        assert "example.txt" in text

    finally:
        await client.close()