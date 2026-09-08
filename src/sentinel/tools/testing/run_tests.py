import asyncio
from pathlib import Path

from sentinel.tools.base import Tool
from sentinel.tools.models import (
    ToolExecutionStatus,
    ToolRequest,
    ToolResult,
)


class RunTestsTool(Tool):
    """Run pytest tests inside the configured repository."""

    def __init__(
        self,
        repository_root: Path,
    ) -> None:
        self._repository_root = repository_root.resolve()

    @property
    def name(self) -> str:
        return "run_tests"

    @property
    def description(self) -> str:
        return "Run pytest tests inside the configured repository."

    async def execute(
        self,
        request: ToolRequest,
    ) -> ToolResult:
        test_path = request.arguments.get(
            "test_path",
            "tests",
        )

        if not isinstance(test_path, str):
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error="Argument 'test_path' must be a string.",
                request_id=request.request_id,
            )

        path = (self._repository_root / test_path).resolve()

        if not self._is_inside_repository(path):
            return ToolResult(
                status=ToolExecutionStatus.DENIED,
                error="Requested path is outside the repository.",
                request_id=request.request_id,
            )

        if not path.exists():
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=f"Test path does not exist: {test_path}",
                request_id=request.request_id,
            )

        process = await asyncio.create_subprocess_exec(
            "pytest",
            str(path),
            cwd=str(self._repository_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        output = stdout.decode(
            "utf-8",
            errors="replace",
        )

        error_output = stderr.decode(
            "utf-8",
            errors="replace",
        )

        combined_output = output

        if error_output:
            combined_output += (
                "\nSTDERR:\n"
                f"{error_output}"
            )

        if process.returncode == 0:
            return ToolResult(
                status=ToolExecutionStatus.SUCCESS,
                output=combined_output,
                request_id=request.request_id,
            )

        return ToolResult(
            status=ToolExecutionStatus.FAILURE,
            output=combined_output,
            error=f"Pytest exited with code {process.returncode}.",
            request_id=request.request_id,
        )

    def _is_inside_repository(
        self,
        path: Path,
    ) -> bool:
        return (
            path == self._repository_root
            or self._repository_root in path.parents
        )
