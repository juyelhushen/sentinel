from sentinel.tools.models import ToolResult, ToolRequest


class ToolGateway:
    """Application boundary for executing tools."""

    async def execute(
            self,
            request: ToolRequest,
    ) -> ToolResult:
        """Execute a tool request."""
        raise NotImplementedError()