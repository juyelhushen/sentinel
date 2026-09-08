from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from sentinel.tools.models import (
    ToolExecutionStatus,
    ToolRequest,
)
from sentinel.tools.testing.run_tests import RunTestsTool


@pytest.mark.asyncio
async def test_run_tests_rejects_invalid_test_path_type(
    tmp_path: Path,
) -> None:
    tool = RunTestsTool(
        repository_root=tmp_path,
    )

    request = ToolRequest(
        tool_name="run_tests",
        arguments={
            "test_path": 123,
        },
    )

    result = await tool.execute(request)

    assert result.status == ToolExecutionStatus.FAILURE
    assert result.error == (
        "Argument 'test_path' must be a string."
    )


@pytest.mark.asyncio
async def test_run_tests_denies_path_outside_repository(
    tmp_path: Path,
) -> None:
    tool = RunTestsTool(
        repository_root=tmp_path,
    )

    request = ToolRequest(
        tool_name="run_tests",
        arguments={
            "test_path": "../outside",
        },
    )

    result = await tool.execute(request)

    assert result.status == ToolExecutionStatus.DENIED


@pytest.mark.asyncio
async def test_run_tests_rejects_missing_test_path(
    tmp_path: Path,
) -> None:
    tool = RunTestsTool(
        repository_root=tmp_path,
    )

    request = ToolRequest(
        tool_name="run_tests",
        arguments={
            "test_path": "tests",
        },
    )

    result = await tool.execute(request)

    assert result.status == ToolExecutionStatus.FAILURE
    assert result.error == (
        "Test path does not exist: tests"
    )


@pytest.mark.asyncio
async def test_run_tests_returns_success(
    tmp_path: Path,
) -> None:
    tests_path = tmp_path / "tests"
    tests_path.mkdir()

    tool = RunTestsTool(
        repository_root=tmp_path,
    )

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (
        b"2 passed\n",
        b"",
    )

    with patch(
        "asyncio.create_subprocess_exec",
        return_value=mock_process,
    ) as mock_create_process:
        result = await tool.execute(
            ToolRequest(
                tool_name="run_tests",
                arguments={
                    "test_path": "tests",
                },
            )
        )

    assert result.status == ToolExecutionStatus.SUCCESS
    assert result.output == "2 passed\n"

    mock_create_process.assert_called_once_with(
        "pytest",
        str(tests_path.resolve()),
        cwd=str(tmp_path.resolve()),
        stdout=pytest.importorskip("asyncio").subprocess.PIPE,
        stderr=pytest.importorskip("asyncio").subprocess.PIPE,
    )


@pytest.mark.asyncio
async def test_run_tests_returns_failure(
    tmp_path: Path,
) -> None:
    tests_path = tmp_path / "tests"
    tests_path.mkdir()

    tool = RunTestsTool(
        repository_root=tmp_path,
    )

    mock_process = AsyncMock()
    mock_process.returncode = 1
    mock_process.communicate.return_value = (
        b"1 failed\n",
        b"AssertionError\n",
    )

    with patch(
        "asyncio.create_subprocess_exec",
        return_value=mock_process,
    ):
        result = await tool.execute(
            ToolRequest(
                tool_name="run_tests",
                arguments={
                    "test_path": "tests",
                },
            )
        )

    assert result.status == ToolExecutionStatus.FAILURE
    assert result.error == (
        "Pytest exited with code 1."
    )

    assert "1 failed" in result.output
    assert "STDERR:" in result.output
    assert "AssertionError" in result.output
