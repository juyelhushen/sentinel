from pathlib import Path

import pytest

from sentinel.tools.filesystem.read_file import ReadFileTool
from sentinel.tools.models import (
    ToolExecutionStatus,
    ToolRequest,
)


@pytest.mark.asyncio
async def test_read_file_reads_file_inside_repository(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "example.txt"
    file_path.write_text("hello sentinel", encoding="utf-8")

    tool = ReadFileTool(tmp_path)

    result = await tool.execute(
        ToolRequest(
            tool_name="read_file",
            arguments={"path": "example.txt"},
        )
    )

    assert result.status == ToolExecutionStatus.SUCCESS
    assert result.output == "hello sentinel"


@pytest.mark.asyncio
async def test_read_file_denies_path_traversal(
    tmp_path: Path,
) -> None:
    outside_file = tmp_path.parent / "secret.txt"
    outside_file.write_text("secret", encoding="utf-8")

    tool = ReadFileTool(tmp_path)

    result = await tool.execute(
        ToolRequest(
            tool_name="read_file",
            arguments={
                "path": "../secret.txt",
            },
        )
    )

    assert result.status == ToolExecutionStatus.DENIED
