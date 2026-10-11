from pathlib import Path

from sentinel.agents.investigator.agent import InvestigatorAgent
from sentinel.agents.planner.agent import PlannerAgent
from sentinel.application.services.investigation_service import InvestigationService
from sentinel.application.tools.local_gateway import LocalToolGateway
from sentinel.bootstrap.tools import create_tool_executor
from sentinel.infrastructure.database.schema import SchemaInitializer
from sentinel.infrastructure.database.sqlite import SQLiteDatabase
from sentinel.infrastructure.persistence.sqllite.execution_repository import (
    SQLiteExecutionRepository,
)
from sentinel.infrastructure.persistence.sqllite.incident_repository import (
    SQLiteIncidentRepository,
)
from sentinel.infrastructure.persistence.sqllite.tool_execution_repository import (
    SQLiteToolExecutionRepository,
)
from sentinel.llm.base import LLMProvider
from sentinel.workflows.sentinel_graph import create_sentinel_graph


def create_investigation_service(
    *,
    llm_provider: LLMProvider,
    repository_root: Path,
    database_path: Path,
) -> InvestigationService:
    """Create the application investigation use case."""

    database = SQLiteDatabase(database_path)
    SchemaInitializer(database).initialize()
    incident_repository = SQLiteIncidentRepository(database)
    execution_repository = SQLiteExecutionRepository(database)
    tool_execution_repository = SQLiteToolExecutionRepository(database)

    tool_executor = create_tool_executor(
        repository_root=repository_root,
        audit_repository=tool_execution_repository,
    )

    planner_agent = PlannerAgent(
        llm_provider=llm_provider,
    )

    investigator_agent = InvestigatorAgent(
        tool_gateway=LocalToolGateway(tool_executor),
    )

    graph = create_sentinel_graph(
        planner_agent=planner_agent,
        investigator_agent=investigator_agent,
    )

    return InvestigationService(
        incident_repository=incident_repository,
        execution_repository=execution_repository,
        graph=graph,
    )
