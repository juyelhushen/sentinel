from sentinel.application.ports.tool_gateway import ToolGateway
from sentinel.tools.executor import ToolExecutor
from sentinel.tools.models import ToolRequest, ToolResult


class LocalToolGateway(ToolGateway):
    """Executes tools directly through Sentinel's ToolExecutor."""

    def __init__(
            self,
            executor: ToolExecutor
    ) -> None:
        self.executor = executor

    async def execute(
            self,
            request: ToolRequest,
    ) -> ToolResult:
        return await self.executor.execute(request)