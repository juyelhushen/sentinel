from pathlib import Path

from sentinel.tools.base import Tool
from sentinel.tools.models import (
    ToolExecutionStatus,
    ToolRequest,
    ToolResult,
)


class SearchFilesTool(Tool):
    """Search text files for a given string."""

    def __init__(self, repository_root: Path) -> None:
        self._repository_root = repository_root.resolve()

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return "Search repository text files for a string."

    async def execute(self, request: ToolRequest) -> ToolResult:
        query = request.arguments.get("query")

        if not isinstance(query, str) or not query.strip():
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error="Argument 'query' must be a non-empty string.",
                request_id=request.request_id,
            )

        matches: list[str] = []

        for path in self._repository_root.rglob("*"):
            if not path.is_file():
                continue

            if not self._should_search(path):
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError, OSError:
                continue

            if query in content:
                matches.append(str(path.relative_to(self._repository_root)))

        return ToolResult(
            status=ToolExecutionStatus.SUCCESS,
            output=sorted(matches),
            request_id=request.request_id,
        )

    def _should_search(self, path: Path) -> bool:
        excluded_directories = {
            ".git",
            ".venv",
            "__pycache__",
            "node_modules",
            ".idea",
            ".pytest_cache",
        }

        return not any(directory in path.parts for directory in excluded_directories)
