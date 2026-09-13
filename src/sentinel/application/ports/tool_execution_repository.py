from abc import ABC

from sentinel.domain.tool_execution import ToolExecution


class ToolExecutionRepository(ABC):
    """Persistence contract for tool execution records."""

    async def save(
        self,
        tool_execution: ToolExecution,
    ) -> None:
        """Persist a tool execution record."""
