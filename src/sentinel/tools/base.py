from abc import ABC, abstractmethod

from sentinel.tools.models import ToolRequest, ToolResult


class Tool(ABC):
    """Base contract for all Sentinel tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique tool name"""

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description suitable for agents/tool discovery."""

    @abstractmethod
    async def execute(self, request: ToolRequest) -> ToolResult:
        """Execute the tool."""
