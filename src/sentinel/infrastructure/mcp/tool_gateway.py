from sentinel.application.ports.tool_gateway import ToolGateway
from sentinel.infrastructure.mcp.client import SentinelMCPClient
from sentinel.tools.models import ToolExecutionStatus, ToolRequest, ToolResult


class MCPToolGateway(ToolGateway):
    """Executes Sentinel tools through an MCP server."""

    def __init__(self, client: SentinelMCPClient) -> None:
        self.client = client

    async def initialize(self) -> None:
        await self.client.list_tools()

    async def execute(self, request: ToolRequest) -> ToolResult:

        if request.tool_name not in self.client.tool_names:
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=f"MCP tool is not available: {request.tool_name}.",
                request_id=request.request_id,
            )

        try:
            result = await self.client.call_tool(
                request.tool_name,
                request.arguments,
            )
        except Exception as exc:
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=f"MCP tool execution failed: {exc}",
                request_id=request.request_id,
            )

        text_items = [item.text for item in result.content if hasattr(item, "text")]

        output = "\n".join(text_items)

        if result.is_error:
            error_text = output or "MCP tool execution failed."
            if error_text.startswith("[DENIED]"):
                return ToolResult(
                    status=ToolExecutionStatus.DENIED,
                    output=output or None,
                    error=error_text,
                    request_id=request.request_id,
                )

            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                output=output or None,
                error=error_text,
                request_id=request.request_id,
            )

        return ToolResult(
            status=ToolExecutionStatus.SUCCESS,
            output=output,
            request_id=request.request_id,
        )
