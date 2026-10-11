import asyncio

from sentinel.application.use_cases.create_incident import (
    CreateIncidentCommand,
    CreateIncidentUseCase,
)
from sentinel.bootstrap.persistence import open_persistence
from sentinel.config.settings import get_settings


def main() -> None:
    """Run Sentinel."""

    async def run() -> None:
        settings = get_settings()
        async with open_persistence(
            settings.database_connection_url,
            schema=settings.database_schema,
            timeout_seconds=settings.database_connect_timeout_seconds,
            pool_size=settings.database_pool_size,
        ) as persistence:
            create_incident = CreateIncidentUseCase(persistence.incidents)
            incident = await create_incident.execute(
                CreateIncidentCommand(
                    title="Example incident",
                    description="Example Sentinel incident",
                    repository="/workspace/example",
                )
            )
            print(f"Created incident: {incident.id}")

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(run())


if __name__ == "__main__":
    main()
