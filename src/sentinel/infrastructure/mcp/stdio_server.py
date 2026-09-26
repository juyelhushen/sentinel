import asyncio
import os
from pathlib import Path

from sentinel.bootstrap.tools import create_tool_executor
from sentinel.infrastructure.mcp.server import run_server

async def main() -> None:

    repository_root = Path(
        os.environ.get("SENTINEL_REPOSITORY_ROOT", Path.cwd())
    ).resolve()

    tool_executor = create_tool_executor(
        repository_root=repository_root,
    )

    await run_server(
        repository_root=repository_root,
        tool_executor=tool_executor,
    )

if __name__ == "__main__":
    asyncio.run(main())