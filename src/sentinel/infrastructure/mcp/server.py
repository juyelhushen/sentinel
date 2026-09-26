from pathlib import Path

from mcp.server.mcpserver import MCPServer

from sentinel.tools.executor import ToolExecutor
from sentinel.tools.models import ToolRequest


class SentinelMCPServer:
    """MCP adapter exposing Sentinel tools."""

    def __init__(
            self,
            repository_root: Path,
            tool_executor: ToolExecutor
    ) -> None:

        self.repository_root = repository_root
        self.tool_executor = tool_executor

        self._server = MCPServer("sentinel")

        self.register_tools()

    def register_tools(self) -> None:
        
        @self._server.tool()
        async def read_file(path: str) -> str:
            """Read a UTF-8 text file from the repository."""
            request = ToolRequest(
                tool_name="read_file",
                arguments={"path": path}
            )

            result = await self.tool_executor.execute(request)

            if not result.succeeded:
                raise RuntimeError(result.error or "read_file execution failed.")

            return str(result.output)

        @self._server.tool()
        async def search_code(
                query: str,
                path: str = '.',
        ) -> str:
            """Search repository source code for a text pattern."""
            request = ToolRequest(
                tool_name="search_code",
                arguments={
                    "query": query,
                    "path": path
                },
            )

            result = await self.tool_executor.execute(request)

            if not result.succeeded:
                raise RuntimeError(result.error or "search_code execution failed.")

            return str(result.output)

        @self._server.tool()
        async def run_tests(path: str) -> str:
            # Map MCP "path" parameter to RunTestsTool's "test_path" argument.
            # RunTestsTool.execute() expects "test_path", not "path".
            request = ToolRequest(
                tool_name="run_tests",
                arguments={"test_path": path},
            )

            result = await self.tool_executor.execute(request)

            if not result.succeeded:
                raise RuntimeError(
                    result.error or "run_tests execution failed."
                )

            return str(result.output)

    @property
    def server(self) -> MCPServer:
        return self._server

async def run_server(
    repository_root: Path,
    tool_executor: ToolExecutor,
) -> None:
    """Run the Sentinel MCP server over stdio."""

    server = SentinelMCPServer(
        repository_root=repository_root,
        tool_executor=tool_executor,
    )

    await server.server.run_stdio_async()

if __name__ == "__main__":
    raise SystemExit(
        "Use the application bootstrap to start the Sentinel MCP server."
    )