from pathlib import Path

import pytest

from sentinel.tools.filesystem.search_code import SearchCodeTool
from sentinel.tools.models import ToolExecutionStatus, ToolRequest


@pytest.mark.asyncio
async def test_search_code_finds_matching_lines(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "service.py"

    source_file.write_text(
        "def validate_token():\n"
        "    return True\n"
        "\n"
        "validate_token()\n",
        encoding="utf-8",
    )

    tool = SearchCodeTool(
        repository_root=tmp_path,
    )

    request = ToolRequest(
        tool_name="search_code",
        arguments={
            "query": "validate_token",
        },
    )

    result = await tool.execute(request)

    assert result.status == ToolExecutionStatus.SUCCESS
    assert result.output == [
        {
            "path": "service.py",
            "line_number": 1,
            "line": "def validate_token():",
        },
        {
            "path": "service.py",
            "line_number": 4,
            "line": "validate_token()",
        },
    ]


@pytest.mark.asyncio
async def test_search_code_returns_empty_results_when_no_match(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "service.py"

    source_file.write_text(
        "def validate_token():\n",
        encoding="utf-8",
    )

    tool = SearchCodeTool(
        repository_root=tmp_path,
    )

    request = ToolRequest(
        tool_name="search_code",
        arguments={
            "query": "missing_function",
        },
    )

    result = await tool.execute(request)

    assert result.status == ToolExecutionStatus.SUCCESS
    assert result.output == []


@pytest.mark.asyncio
async def test_search_code_rejects_missing_query(
    tmp_path: Path,
) -> None:
    tool = SearchCodeTool(
        repository_root=tmp_path,
    )

    request = ToolRequest(
        tool_name="search_code",
        arguments={},
    )

    result = await tool.execute(request)

    assert result.status == ToolExecutionStatus.FAILURE
    assert result.error == "Argument 'query' must be a string."


@pytest.mark.asyncio
async def test_search_code_rejects_empty_query(
    tmp_path: Path,
) -> None:
    tool = SearchCodeTool(
        repository_root=tmp_path,
    )

    request = ToolRequest(
        tool_name="search_code",
        arguments={
            "query": "   ",
        },
    )

    result = await tool.execute(request)

    assert result.status == ToolExecutionStatus.FAILURE
    assert result.error == "Argument 'query' must not be empty."