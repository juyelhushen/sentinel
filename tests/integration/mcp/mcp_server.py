from pathlib import Path

from sentinel.bootstrap.tools import create_tool_executor
from sentinel.infrastructure.database.schema import SchemaInitializer
from sentinel.infrastructure.database.sqlite import SQLiteDatabase
from sentinel.infrastructure.mcp.server import run_server


async def main() -> None:
    repository_root = Path.cwd()

    database = SQLiteDatabase(
        repository_root / ".sentinel-test.db",
    )

    SchemaInitializer(database).initialize()

    tool_executor = create_tool_executor(
        repository_root=repository_root,
    )

    await run_server(
        repository_root=repository_root,
        tool_executor=tool_executor,
    )