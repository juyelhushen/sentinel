from contextlib import AsyncExitStack
from json import tool

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class SentinelMCPClient:
    """Client for communicating with a Sentinel MCP server."""

    def __init__(self) -> None:
        self._exit_stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tool_names: set[str] = set()

    async def connect(
        self,
        command: str,
        args: list[str],
        env: dict[str, str] | None = None,
    ) -> None:

        server_parameters = StdioServerParameters(
            command=command,
            args=args,
            env=env,
        )

        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(server_parameters)
        )

        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        await self._session.initialize()

    async def list_tools(self):
        if self._session is None:
            raise RuntimeError("MCP client is not connected.")

        result = await self._session.list_tools()

        return result.tools

    async def call_tool(self, name: str, args: dict):
        if self._session is None:
            raise RuntimeError("MCP client is not connected.")

        return await self._session.call_tool(name, args)

    async def close(self) -> None:
        await self._exit_stack.aclose()

    async def list_tool_names(self) -> set[str]:
        if self._session is None:
            raise RuntimeError("MCP client is not connected.")

        result = await self._session.list_tools()
        self._tool_names = {tool.name for tool in result.tools}
        return set(self._tool_names)

    @property
    def tool_names(self) -> frozenset[str]:
        return frozenset(self._tool_names)
