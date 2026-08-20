from pathlib import Path

from sentinel.tools.base import Tool
from sentinel.tools.models import ToolExecutionStatus, ToolRequest, ToolResult


class ListDirectoryTool(Tool):
    """List files and directories inside a repository"""

    def __init__(self, repository_root: Path) -> None:
        self._repository_root = repository_root.resolve()

    @property
    def name(self) -> str:
        return "list-directory"

    @property
    def description(self) -> str:
        return "List files and directories inside the configured repository."

    async def execute(self, request: ToolRequest) -> ToolResult:
        path_argument = request.arguments.get("path", ".")

        if not isinstance(path_argument, str):
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error="Argument must be a string.",
                request_id=request.request_id,
            )

        path = (self._repository_root / path_argument).resolve()

        if not self._is_inside_repository(path):
            return ToolResult(
                status=ToolExecutionStatus.DENIED,
                error="Repository is not inside the configured repository.",
                request_id=request.request_id,
            )

        if not path.exists():
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=f"Directory does not exist: {path_argument}",
                request_id=request.request_id,
            )

        if not path.is_dir():
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=f"Directory is not a directory: {path_argument}",
                request_id=request.request_id,
            )

        entries = sorted(entry.name for entry in path.iterdir())

        return ToolResult(
            status=ToolExecutionStatus.SUCCESS,
            output=entries,
            request_id=request.request_id,
        )

    def _is_inside_repository(self, path: Path) -> bool:
        return path == self._repository_root or (self._repository_root in path.parents)
