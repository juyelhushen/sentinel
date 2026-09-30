import sys
from pathlib import Path

import pytest

from sentinel.infrastructure.mcp.client import SentinelMCPClient


@pytest.mark.asyncio
async def test_mcp_client_rejects_disallowed_read_file_under_restricted_policy(
    tmp_path: Path,
):
    # This temporary server simulates a restricted MCP deployment where only
    # search_code is allowed. The policy should deny read_file before the tool body runs.
    marker_path = tmp_path / "read_file_was_called.txt"
    server_script = tmp_path / "restricted_mcp_server.py"
    server_script.write_text(
        "import asyncio\n"
        "import os\n"
        "from pathlib import Path\n\n"
        "from sentinel.infrastructure.mcp.server import SentinelMCPServer\n"
        "from sentinel.tools.executor import ToolExecutor\n"
        "from sentinel.tools.models import ToolExecutionStatus, ToolRequest, ToolResult\n"
        "from sentinel.tools.policy import ToolPolicy\n"
        "from sentinel.tools.registry import ToolRegistry\n\n"
        "class ReadFileSpy:\n"
        "    def __init__(self, marker_path: str) -> None:\n"
        "        self._marker_path = Path(marker_path)\n"
        "    @property\n"
        "    def name(self):\n"
        "        return 'read_file'\n"
        "    @property\n"
        "    def description(self):\n"
        "        return 'spy'\n"
        "    async def execute(self, request: ToolRequest) -> ToolResult:\n"
        "        self._marker_path.write_text('called', encoding='utf-8')\n"
        "        return ToolResult(status=ToolExecutionStatus.SUCCESS, output='should not run', request_id=request.request_id)\n\n"
        "class SearchCodeSpy:\n"
        "    @property\n"
        "    def name(self):\n"
        "        return 'search_code'\n"
        "    @property\n"
        "    def description(self):\n"
        "        return 'search'\n"
        "    async def execute(self, request: ToolRequest) -> ToolResult:\n"
        "        return ToolResult(status=ToolExecutionStatus.SUCCESS, output='ok', request_id=request.request_id)\n\n"
        "async def main() -> None:\n"
        "    repository_root = Path.cwd()\n"
        "    registry = ToolRegistry()\n"
        "    registry.register(ReadFileSpy(os.environ['SENTINEL_MARKER_PATH']))\n"
        "    registry.register(SearchCodeSpy())\n"
        "    policy = ToolPolicy(allowed_tools={'search_code'})\n"
        "    tool_executor = ToolExecutor(registry=registry, policy=policy)\n"
        "    server = SentinelMCPServer(repository_root=repository_root, tool_executor=tool_executor)\n"
        "    await server.server.run_stdio_async()\n\n"
        "asyncio.run(main())\n",
        encoding="utf-8",
    )

    client = SentinelMCPClient()

    try:
        await client.connect(
            command=sys.executable,
            args=[str(server_script)],
            env={
                "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
                "SENTINEL_MARKER_PATH": str(marker_path),
            },
        )

        result = await client.call_tool(
            "read_file",
            {
                "path": "tests/fixtures/mcp/example.txt",
            },
        )

        # The MCP tool is denied by the same executor policy path; the read_file
        # tool body never writes the marker file.
        assert result.is_error is True
        assert not marker_path.exists()

    finally:
        await client.close()


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

        assert tool_names == {"read_file", "search_code", "run_tests"}
        assert client.tool_names == frozenset({"read_file", "search_code", "run_tests"})

        read_file = client.get_tool("read_file")
        assert read_file.name == "read_file"
        assert read_file.description
        assert isinstance(read_file.input_schema, dict)
        assert read_file.input_schema["type"] == "object"
        assert "properties" in read_file.input_schema
        assert "path" in read_file.input_schema["properties"]
        assert read_file.input_schema["required"] == ["path"]

        result = await client.call_tool(
            "read_file",
            {
                "path": "tests/fixtures/mcp/example.txt",
            },
        )

        assert result.is_error is False

        text = "\n".join(item.text for item in result.content if hasattr(item, "text"))

        assert "Hello from Sentinel MCP!" in text

        assert {tool.name for tool in client.tools} == {"read_file", "search_code", "run_tests"}

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

        text = "\n".join(item.text for item in result.content if hasattr(item, "text"))

        assert "example.txt" in text

    finally:
        await client.close()


@pytest.mark.asyncio
async def test_mcp_client_can_call_run_tests():
    # Set repository root to match other integration tests.
    # Required so MCP server uses correct working directory for relative paths.
    repository_root = Path(__file__).resolve().parents[3]

    client = SentinelMCPClient()

    try:
        # Pass repository_root to MCP server via environment variable.
        # Without this, server defaults to current working directory,
        # causing test discovery to fail.
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

        result = await client.call_tool(
            "run_tests",
            {
                "path": "tests/unit/infrastructure/mcp/test_server.py",
            },
        )

        assert result.is_error is False
        assert result.content

        text = "\n".join(item.text for item in result.content if hasattr(item, "text"))

        assert "passed" in text.lower()

    finally:
        await client.close()
