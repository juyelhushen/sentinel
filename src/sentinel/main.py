from sentinel.application.use_cases.create_incident import (
    CreateIncidentCommand,
    CreateIncidentUseCase,
)
from sentinel.infrastructure.dependencies.database import (
    create_database_connection,
)
from sentinel.infrastructure.dependencies.repositories import (
    create_incident_repository,
)


def main() -> None:
    """Run Sentinel."""

    connection = create_database_connection()

    repository = create_incident_repository(connection)

    create_incident = CreateIncidentUseCase(repository)

    incident = create_incident.execute(
        CreateIncidentCommand(
            title="Example incident",
            description="Example Sentinel incident",
            repository="/workspace/example",
        )
    )

    print(f"Created incident: {incident.id}")

    connection.close()


if __name__ == "__main__":
    main()
