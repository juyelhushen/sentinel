from uuid import uuid4

from sentinel.domain.tool_execution import ToolExecution
from sentinel.infrastructure.persistence.sqllite.tool_execution_repository import SQLiteToolExecutionRepository
from sentinel.tools.models import ToolExecutionStatus


async def test_save_and_get_by_execution_id(tmp_path):
    database_path = tmp_path / "sentinel.db"

    repository = SQLiteToolExecutionRepository(
        database_path=database_path,
    )

    await repository.initialize()

    execution_id = uuid4()

    tool_execution = ToolExecution(
        tool_name="read_file",
        status=ToolExecutionStatus.SUCCESS,
        execution_id=execution_id,
        arguments={
            "path": "src/sentinel/example.py",
        },
        output="print('hello')",
    )

    await repository.save(tool_execution)

    records = await repository.get_by_execution_id(
        execution_id,
    )

    assert len(records) == 1

    record = records[0]

    assert record.request_id == tool_execution.request_id
    assert record.tool_name == "read_file"
    assert record.status == ToolExecutionStatus.SUCCESS
    assert record.execution_id == execution_id
    assert record.arguments == {
        "path": "src/sentinel/example.py",
    }
    assert record.output == "print('hello')"
    assert record.error is None
    assert record.started_at == tool_execution.started_at
    assert record.completed_at == tool_execution.completed_at


async def test_save_and_get_failed_tool_execution(tmp_path):
    database_path = tmp_path / "sentinel.db"

    repository = SQLiteToolExecutionRepository(
        database_path=database_path,
    )

    await repository.initialize()

    execution_id = uuid4()

    tool_execution = ToolExecution(
        tool_name="run_tests",
        status=ToolExecutionStatus.FAILURE,
        execution_id=execution_id,
        arguments={
            "test_path": "tests",
        },
        error="Pytest exited with code 1.",
    )

    await repository.save(tool_execution)

    records = await repository.get_by_execution_id(
        execution_id,
    )

    assert len(records) == 1

    record = records[0]

    assert record.tool_name == "run_tests"
    assert record.status == ToolExecutionStatus.FAILURE
    assert record.arguments == {
        "test_path": "tests",
    }
    assert record.output is None
    assert record.error == "Pytest exited with code 1."


async def test_save_and_get_denied_tool_execution(tmp_path):
    database_path = tmp_path / "sentinel.db"

    repository = SQLiteToolExecutionRepository(
        database_path=database_path,
    )

    await repository.initialize()

    execution_id = uuid4()

    tool_execution = ToolExecution(
        tool_name="delete_file",
        status=ToolExecutionStatus.DENIED,
        execution_id=execution_id,
        arguments={
            "path": "important.txt",
        },
        error="Tool is not allowed.",
    )

    await repository.save(tool_execution)

    records = await repository.get_by_execution_id(
        execution_id,
    )

    assert len(records) == 1

    record = records[0]

    assert record.tool_name == "delete_file"
    assert record.status == ToolExecutionStatus.DENIED
    assert record.arguments == {
        "path": "important.txt",
    }
    assert record.error == "Tool is not allowed."


async def test_get_by_execution_id_returns_empty_for_unknown_execution(
    tmp_path,
):
    database_path = tmp_path / "sentinel.db"

    repository = SQLiteToolExecutionRepository(
        database_path=database_path,
    )

    await repository.initialize()

    records = await repository.get_by_execution_id(
        uuid4(),
    )

    assert records == []


async def test_tool_executions_survive_repository_recreation(
    tmp_path,
):
    database_path = tmp_path / "sentinel.db"

    execution_id = uuid4()

    first_repository = SQLiteToolExecutionRepository(
        database_path=database_path,
    )

    await first_repository.initialize()

    tool_execution = ToolExecution(
        tool_name="search_code",
        status=ToolExecutionStatus.SUCCESS,
        execution_id=execution_id,
        arguments={
            "query": "ToolExecutor",
        },
        output="src/sentinel/tools/executor.py:10",
    )

    await first_repository.save(tool_execution)

    second_repository = SQLiteToolExecutionRepository(
        database_path=database_path,
    )

    records = await second_repository.get_by_execution_id(
        execution_id,
    )

    assert len(records) == 1
    assert records[0].request_id == tool_execution.request_id
    assert records[0].tool_name == "search_code"
    assert records[0].status == ToolExecutionStatus.SUCCESS
    assert records[0].arguments == {
        "query": "ToolExecutor",
    }
    assert records[0].output == (
        "src/sentinel/tools/executor.py:10"
    )