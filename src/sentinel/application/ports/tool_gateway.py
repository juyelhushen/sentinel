from sentinel.tools.models import ToolRequest, ToolResult


class ToolGateway:
    """Application boundary for executing tools."""

    async def execute(
        self,
        request: ToolRequest,
    ) -> ToolResult:
        """Execute a tool request."""
        raise NotImplementedError()
