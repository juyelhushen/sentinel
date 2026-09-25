from pathlib import Path

from sentinel.application.ports.tool_execution_repository import ToolExecutionRepository
from sentinel.tools.executor import ToolExecutor
from sentinel.tools.filesystem.read_file import ReadFileTool
from sentinel.tools.filesystem.search_code import SearchCodeTool
from sentinel.tools.policy import ToolPolicy
from sentinel.tools.registry import ToolRegistry
from sentinel.tools.testing.run_tests import RunTestsTool


def create_tool_executor(
    repository_root: Path,
    audit_repository: ToolExecutionRepository | None = None,
) -> ToolExecutor:
    registry = ToolRegistry()

    registry.register(
        ReadFileTool(repository_root=repository_root)
    )

    registry.register(
        SearchCodeTool(repository_root=repository_root)
    )

    registry.register(
        RunTestsTool(repository_root=repository_root)
    )

    policy = ToolPolicy(
        allowed_tools={
            "read_file",
            "search_code",
            "run_tests",
        }
    )

    return ToolExecutor(
        registry=registry,
        policy=policy,
        audit_repository=audit_repository,
    )