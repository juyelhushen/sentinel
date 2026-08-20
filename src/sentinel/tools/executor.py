from sentinel.tools.models import (
    ToolExecutionStatus,
    ToolRequest,
    ToolResult,
)
from sentinel.tools.policy import ToolPolicy
from sentinel.tools.registry import ToolRegistry


class ToolExecutor:
    """Safely executes registered tools."""

    def __init__(
        self,
        registry: ToolRegistry,
        policy: ToolPolicy,
    ) -> None:
        self._registry = registry
        self._policy = policy

    async def execute(self, request: ToolRequest) -> ToolResult:
        """Validate and execute a tool request."""

        if not self._registry.contains(request.tool_name):
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=f"Unknown tool: {request.tool_name}",
                request_id=request.request_id,
            )

        if not self._policy.is_allowed(request):
            return ToolResult(
                status=ToolExecutionStatus.DENIED,
                error=f"Tool execution denied: {request.tool_name}",
                request_id=request.request_id,
            )

        tool = self._registry.get(request.tool_name)

        return await tool.execute(request)
