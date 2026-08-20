from pathlib import Path

from sentinel.tools.executor import ToolExecutor
from sentinel.tools.filesystem.list_directory import ListDirectoryTool
from sentinel.tools.filesystem.read_file import ReadFileTool
from sentinel.tools.filesystem.search_files import SearchFilesTool
from sentinel.tools.policy import ToolPolicy
from sentinel.tools.registry import ToolRegistry


def create_tool_executor(repository_root: Path) -> ToolExecutor:
    """Create the configured sentinel tool executor."""

    registry = ToolRegistry()

    registry.register(ReadFileTool(repository_root))

    registry.register(ListDirectoryTool(repository_root))

    registry.register(SearchFilesTool(repository_root))

    policy = ToolPolicy(
        allowed_tools={
            "read_file",
            "list_directory",
            "search_files",
        }
    )

    return ToolExecutor(
        registry=registry,
        policy=policy,
    )
