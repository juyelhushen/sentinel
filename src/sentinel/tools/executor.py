from datetime import UTC, datetime

from sentinel.application.ports.tool_execution_repository import (
    ToolExecutionRepository,
)
from sentinel.domain.tool_execution import ToolExecution
from sentinel.tools.models import ToolExecutionStatus, ToolRequest, ToolResult
from sentinel.tools.policy import ToolPolicy
from sentinel.tools.registry import ToolRegistry


class ToolExecutor:
    """Safely executes registered tools."""

    def __init__(
        self,
        registry: ToolRegistry,
        policy: ToolPolicy,
        audit_repository: ToolExecutionRepository | None = None,
    ) -> None:
        self._registry = registry
        self._policy = policy
        self._audit_repository = audit_repository

    async def execute(self, request: ToolRequest) -> ToolResult:
        """Validate, execute, and audit a tool request."""

        started_at = datetime.now(UTC)

        if not self._registry.contains(request.tool_name):
            result = ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=f"Unknown tool: {request.tool_name}",
                request_id=request.request_id,
            )

            await self._audit(
                request=request,
                result=result,
                started_at=started_at,
            )

            return result

        if not self._policy.is_allowed(request):
            result = ToolResult(
                status=ToolExecutionStatus.DENIED,
                error=f"Tool execution denied: {request.tool_name}",
                request_id=request.request_id,
            )

            await self._audit(
                request=request,
                result=result,
                started_at=started_at,
            )

            return result

        tool = self._registry.get(request.tool_name)

        result = await tool.execute(request)

        await self._audit(
            request=request,
            result=result,
            started_at=started_at,
        )

        return result

    async def _audit(
        self,
        request: ToolRequest,
        result: ToolResult,
        started_at: datetime,
    ) -> None:
        """Persist an audit record when auditing is configured."""

        if self._audit_repository is None:
            return

        await self._audit_repository.save(
            ToolExecution(
                tool_name=request.tool_name,
                status=result.status,
                execution_id=request.execution_id,
                arguments=request.arguments,
                output=(str(result.output) if result.output is not None else None),
                error=result.error,
                request_id=request.request_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
        )
