from sentinel.application.ports.tool_gateway import ToolGateway
from sentinel.infrastructure.mcp.client import SentinelMCPClient
from sentinel.tools.models import ToolRequest, ToolResult, ToolExecutionStatus


class MCPToolGateway(ToolGateway):
    """Executes Sentinel tools through an MCP server."""

    def __init__(
            self,
            client: SentinelMCPClient
    ) -> None:
        self.client = client

    async def execute(
            self,
            request:ToolRequest
    ) -> ToolResult:

        result = await self.client.call_tool(
            request.tool_name,
            request.arguments,
        )

        output = "\n".join(
            item.text
            for item in result.content
            if hasattr(item, "text")
        )

        if result.is_error:
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                output=output or None,
                error=output or "MCP tool execution failed.",
                request_id=request.request_id,
            )

        return ToolResult(
            status=ToolExecutionStatus.SUCCESS,
            output=output,
            request_id=request.request_id,
        )