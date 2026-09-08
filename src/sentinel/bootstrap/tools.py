from pathlib import Path

from sentinel.tools.executor import ToolExecutor
from sentinel.tools.filesystem.read_file import ReadFileTool
from sentinel.tools.filesystem.search_code import SearchCodeTool
from sentinel.tools.policy import ToolPolicy
from sentinel.tools.registry import ToolRegistry
from sentinel.tools.testing.run_tests import RunTestsTool


def create_tool_executor(
        repository_root: Path
)-> ToolExecutor:

    """Create configured sentinel tool executor."""

    registry = ToolRegistry()

    registry.register(
        ReadFileTool(
            repository_root=repository_root,
        )
    )

    registry.register(
        SearchCodeTool(
            repository_root=repository_root,
        )
    )

    registry.register(
        RunTestsTool(
            repository_root=repository_root,
        )
    )

    policy= ToolPolicy(
        allowed_tools={
            "read_file",
            "search_code",
            "run_tests",
        }
    )

    return ToolExecutor(
        registry=registry,
        policy=policy,
    )

