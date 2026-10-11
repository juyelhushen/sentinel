from unittest.mock import AsyncMock, Mock

from sentinel.infrastructure.database.postgres import PostgreSQLDatabase
from sentinel.infrastructure.database.postgres_schema import initialize_postgres_schema


async def test_schema_version_prevents_repeated_migration() -> None:
    database = PostgreSQLDatabase("postgresql://example.invalid/db")
    cursor = AsyncMock()
    cursor.fetchall.side_effect = [[], [{"version": 1}]]
    connection = AsyncMock()
    connection.execute.return_value = cursor
    context = AsyncMock()
    context.__aenter__.return_value = connection
    database.connection = Mock(return_value=context)

    await initialize_postgres_schema(database)
    first_count = connection.execute.await_count
    await initialize_postgres_schema(database)
    initial_statements = [
        str(call.args[0]) for call in connection.execute.await_args_list[:first_count]
    ]
    repeated_statements = [
        str(call.args[0]) for call in connection.execute.await_args_list[first_count:]
    ]
    assert any(
        "CREATE TABLE incidents" in statement for statement in initial_statements
    )
    assert any(
        "INSERT INTO schema_migrations" in statement for statement in initial_statements
    )
    assert not any(
        "CREATE TABLE incidents" in statement for statement in repeated_statements
    )
    assert not any(
        statement.lstrip().startswith(("DROP ", "DELETE ", "TRUNCATE "))
        for statement in initial_statements
    )
    assert any(
        "pg_advisory_xact_lock" in statement for statement in repeated_statements
    )
    assert context.__aexit__.await_count == 2
