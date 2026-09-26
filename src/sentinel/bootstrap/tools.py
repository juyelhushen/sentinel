from pathlib import Path

from sentinel.application.ports.tool_execution_repository import ToolExecutionRepository
from sentinel.tools.executor import ToolExecutor
from sentinel.tools.filesystem.list_directory import ListDirectoryTool
from sentinel.tools.filesystem.read_file import ReadFileTool
from sentinel.tools.filesystem.search_code import SearchCodeTool
from sentinel.tools.filesystem.search_files import SearchFilesTool
from sentinel.tools.policy import ToolPolicy
from sentinel.tools.registry import ToolRegistry
from sentinel.tools.testing.run_tests import RunTestsTool


def create_tool_executor(
    repository_root: Path,
    audit_repository: ToolExecutionRepository | None = None,
) -> ToolExecutor:
    """Create the canonical tool executor with all registered tools.
    
    Registers:
    - read_file: Read file contents
    - search_code: Search code with semantic understanding
    - run_tests: Run test suites
    - list_directory: List directory contents
    - search_files: Search files for text patterns
    """
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

    registry.register(
        ListDirectoryTool(repository_root=repository_root)
    )

    registry.register(
        SearchFilesTool(repository_root=repository_root)
    )

    policy = ToolPolicy(
        allowed_tools={
            "read_file",
            "search_code",
            "run_tests",
            "list-directory",
            "search_files",
        }
    )

    return ToolExecutor(
        registry=registry,
        policy=policy,
        audit_repository=audit_repository,
    )