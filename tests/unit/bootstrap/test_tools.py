from pathlib import Path

import pytest

from sentinel.bootstrap.tools import create_tool_executor
from sentinel.tools.models import ToolExecutionStatus, ToolRequest


@pytest.mark.asyncio
async def test_create_tool_executor_registers_read_file_tool(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "example.txt"

    file_path.write_text(
        "hello sentinel",
        encoding="utf-8",
    )

    executor = create_tool_executor(
        repository_root=tmp_path,
    )

    result = await executor.execute(
        ToolRequest(
            tool_name="read_file",
            arguments={
                "path": "example.txt",
            },
        )
    )

    assert result.status == ToolExecutionStatus.SUCCESS
    assert result.output == "hello sentinel"


@pytest.mark.asyncio
async def test_create_tool_executor_registers_search_code_tool(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "example.py"

    file_path.write_text(
        "def validate_token():\n"
        "    return True\n",
        encoding="utf-8",
    )

    executor = create_tool_executor(
        repository_root=tmp_path,
    )

    result = await executor.execute(
        ToolRequest(
            tool_name="search_code",
            arguments={
                "query": "validate_token",
            },
        )
    )

    assert result.status == ToolExecutionStatus.SUCCESS
    assert result.output == [
        {
            "path": "example.py",
            "line_number": 1,
            "line": "def validate_token():",
        }
    ]


@pytest.mark.asyncio
async def test_create_tool_executor_registers_run_tests_tool(
    tmp_path: Path,
) -> None:
    tests_path = tmp_path / "tests"
    tests_path.mkdir()

    executor = create_tool_executor(
        repository_root=tmp_path,
    )

    result = await executor.execute(
        ToolRequest(
            tool_name="run_tests",
            arguments={
                "test_path": "missing_tests",
            },
        )
    )

    assert result.status == ToolExecutionStatus.FAILURE
    assert result.error == (
        "Test path does not exist: missing_tests"
    )