from pathlib import Path

from sentinel.agents.investigator.agent import InvestigatorAgent
from sentinel.agents.planner.agent import PlannerAgent
from sentinel.application.services.investigation_service import InvestigationService
from sentinel.bootstrap.tools import create_tool_executor
from sentinel.infrastructure.persistence.sqlite_incident_repository import (
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

    incident_repository = SQLiteIncidentRepository(
        database_path=database_path,
    )

    tool_execution_repository = SQLiteToolExecutionRepository(
        database_path=database_path,
    )

    tool_executor = create_tool_executor(
        repository_root=repository_root,
        audit_repository=tool_execution_repository,
    )

    planner_agent = PlannerAgent(
        llm_provider=llm_provider,
    )

    investigator_agent = InvestigatorAgent(
        tool_executor=tool_executor,
    )

    graph = create_sentinel_graph(
        planner_agent=planner_agent,
        investigator_agent=investigator_agent,
    )

    return InvestigationService(
        incident_repository=incident_repository,
        execution_repository=tool_execution_repository,
        graph=graph,
    )
