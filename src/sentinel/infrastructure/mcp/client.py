from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from sentinel.infrastructure.mcp.models import MCPTool


class SentinelMCPClient:
    """Client for communicating with a Sentinel MCP server."""

    def __init__(self) -> None:
        self._exit_stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tools: dict[str, MCPTool] = {}

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

    # async def list_tools(self):
    #     if self._session is None:
    #         raise RuntimeError("MCP client is not connected.")
    #
    #     result = await self._session.list_tools()
    #
    #     return result.tools

    async def call_tool(self, name: str, args: dict):
        if self._session is None:
            raise RuntimeError("MCP client is not connected.")

        return await self._session.call_tool(name, args)

    async def close(self) -> None:
        await self._exit_stack.aclose()


    async def list_tools(self) -> tuple[MCPTool, ...]:
        if self._session is None:
            raise RuntimeError("MCP client is not connected.")

        result = await self._session.list_tools()

        tools = tuple(
            MCPTool(
                name=tool.name,
                description=tool.description or "",
                input_schema=dict(tool.input_schema or {}),
            )
            for tool in result.tools
        )

        self._tools = {tool.name: tool for tool in tools}

        return tools

    def get_tool(self, name: str) -> MCPTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ValueError(f"MCP tool is not discovered: {name}") from exc

    @property
    def tools(self) -> tuple[MCPTool, ...]:
        return tuple(self._tools.values())

    @property
    def tool_names(self) -> frozenset[str]:
        return frozenset(self._tools)



