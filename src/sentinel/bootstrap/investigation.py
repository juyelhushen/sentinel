from pathlib import Path

from sentinel.application.services.investigation_service import InvestigationService
from sentinel.bootstrap.application import create_sentinel_application
from sentinel.bootstrap.persistence import Persistence, create_persistence
from sentinel.infrastructure.database.schema import SchemaInitializer
from sentinel.infrastructure.database.sqlite import SQLiteDatabase
from sentinel.llm.base import LLMProvider


def create_investigation_service(
    *,
    llm_provider: LLMProvider,
    repository_root: Path,
    database_path: Path | None = None,
    persistence: Persistence | None = None,
) -> InvestigationService:
    """Create the application investigation use case."""

    if persistence is None:
        if database_path is None:
            raise ValueError("Provide persistence or a SQLite database path.")
        database = SQLiteDatabase(database_path)
        SchemaInitializer(database).initialize()
        persistence = create_persistence(database)

    graph = create_sentinel_application(
        llm_provider=llm_provider,
        repository_root=repository_root,
        persistence=persistence,
    )

    return InvestigationService(
        incident_repository=persistence.incidents,
        execution_repository=persistence.executions,
        graph=graph,
    )
