from pathlib import Path

from sentinel.tools.base import Tool
from sentinel.tools.models import ToolExecutionStatus, ToolRequest, ToolResult


class SearchCodeTool(Tool):
    """Search for text inside files in the configured repository."""

    def __init__(
            self,
            repository_root: Path,
    ) -> None:
        self._repository_root = repository_root.resolve()

    @property
    def name(self) -> str:
        return "search_code"

    @property
    def description(self) -> str:
        return "Search for text inside files in the configured repository."

    async def execute( 
            self, 
            request: ToolRequest, 
    ) -> ToolResult:

        query = request.arguments.get("query")

        if not isinstance(query, str):
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error="Argument 'query' must be a string.",
                request_id=request.request_id,
            )

        if not query.strip():
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error="Argument 'query' must not be empty.",
                request_id=request.request_id,
            )

        matches = []

        for path in self._repository_root.rglob("*"):
            if not path.is_file():
                continue

            if not self._is_inside_repository(path):
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            for line_number, line in enumerate(
                    content.splitlines(),
                    start=1,
            ):
                if query in line:
                    matches.append(
                        {
                            "path": str(
                                path.relative_to(self._repository_root)
                            ),
                            "line_number": line_number,
                            "line": line,
                        }
                    )

        return ToolResult(
            status=ToolExecutionStatus.SUCCESS,
            output=matches,
            request_id=request.request_id,
        )

    def _is_inside_repository(self, path: Path) -> bool:
        resolved_path = path.resolve()

        return (
            resolved_path == self._repository_root
            or self._repository_root in resolved_path.parents
        )