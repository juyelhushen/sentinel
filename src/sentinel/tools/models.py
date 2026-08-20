from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class ToolExecutionStatus(StrEnum):
    """Possible outcomes of a tool execution."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


@dataclass(frozen=True)
class ToolRequest:
    """Request to execute a tool."""

    tool_name: str
    arguments: dict[str, Any]
    execution_id: UUID | None = None
    request_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ToolResult:
    """Standardized result returned by a tool."""

    status: ToolExecutionStatus
    output: Any = None
    error: str | None = None
    request_id: UUID | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether the tool execution succeeded."""
        return self.status == ToolExecutionStatus.SUCCESS
