from pathlib import Path

from sentinel.tools.base import Tool
from sentinel.tools.models import ToolExecutionStatus, ToolRequest, ToolResult


class ReadFileTool(Tool):
    """Read a file inside the configured repository."""

    def __init__(self, repository_root: Path) -> None:
        self._repository_root = repository_root

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents ot a text file inside the configured repository."

    async def execute(self, request: ToolRequest) -> ToolResult:
        path_argument = request.arguments.get("path")

        if not isinstance(path_argument, str):
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error="Argument 'path' must be a string.",
                request_id=request.request_id,
            )

        path = (self._repository_root / path_argument).resolve()

        if not self._is_inside_repository(path):
            return ToolResult(
                status=ToolExecutionStatus.DENIED,
                error="Requested path is outside the repository.",
                request_id=request.request_id,
            )

        if not path.exists():
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=f"File does not exist: {path_argument}",
                request_id=request.request_id,
            )

        if not path.is_file():
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=f"Path is not a file: {path_argument}",
                request_id=request.request_id,
            )

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=f"File is not valid UTF-8 text: {path_argument}",
                request_id=request.request_id,
            )

        return ToolResult(
            status=ToolExecutionStatus.SUCCESS,
            output=content,
            request_id=request.request_id,
        )

    def _is_inside_repository(self, path: Path) -> bool:
        return path == self._repository_root or (self._repository_root in path.parents)
