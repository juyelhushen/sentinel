from pathlib import Path
from typing import Any

from sentinel.agents.investigator.agent import InvestigatorAgent
from sentinel.agents.planner.agent import PlannerAgent
from sentinel.agents.verification.verification_agent import VerificationAgent
from sentinel.application.ports.execution_repository import ExecutionRepository
from sentinel.application.ports.incident_repository import IncidentRepository
from sentinel.application.ports.repair_approval_gate import RepairApprovalGate
from sentinel.application.ports.repair_repository import RepairRepository
from sentinel.application.repair.repair_agent import RepairAgent
from sentinel.application.services.repair_execution_service import (
    RepairExecutionService,
)
from sentinel.application.tools.local_gateway import LocalToolGateway
from sentinel.bootstrap.tools import create_tool_executor
from sentinel.domain.repair.retry import RepairRetryPolicy
from sentinel.infrastructure.database.sqlite import SQLiteDatabase
from sentinel.infrastructure.persistence.sqllite.execution_repository import (
    SQLiteExecutionRepository,
)
from sentinel.infrastructure.persistence.sqllite.incident_repository import (
    SQLiteIncidentRepository,
)
from sentinel.infrastructure.persistence.sqllite.repair_repository import (
    SQLiteRepairRepository,
)
from sentinel.infrastructure.persistence.sqllite.tool_execution_repository import (
    SQLiteToolExecutionRepository,
)
from sentinel.llm.base import LLMProvider
from sentinel.workflows.sentinel_graph import create_sentinel_graph


def create_sentinel_application(
    *,
    llm_provider: LLMProvider,
    repository_root: Path,
    enable_repair: bool = False,
    verification_path: str = "tests",
    retry_policy: RepairRetryPolicy | None = None,
    approval_gate: RepairApprovalGate | None = None,
    database: SQLiteDatabase | None = None,
    repair_repository: RepairRepository | None = None,
    incident_repository: IncidentRepository | None = None,
    execution_repository: ExecutionRepository | None = None,
) -> Any:
    """Create the complete Sentinel application."""

    tool_executor = create_tool_executor(
        repository_root=repository_root,
        audit_repository=(
            SQLiteToolExecutionRepository(database) if database is not None else None
        ),
    )

    local_gateway = LocalToolGateway(
        executor=tool_executor,
    )

    planner_agent = PlannerAgent(
        llm_provider=llm_provider,
    )

    investigator_agent = InvestigatorAgent(
        tool_gateway=local_gateway,
    )

    if enable_repair:
        repair_repository = repair_repository or (
            SQLiteRepairRepository(database) if database is not None else None
        )
        incident_repository = incident_repository or (
            SQLiteIncidentRepository(database) if database is not None else None
        )
        execution_repository = execution_repository or (
            SQLiteExecutionRepository(database) if database is not None else None
        )

        return create_sentinel_graph(
            planner_agent,
            investigator_agent,
            repair_agent=RepairAgent(llm_provider),
            repair_execution_service=RepairExecutionService(local_gateway),
            verification_agent=VerificationAgent(local_gateway),
            verification_path=verification_path,
            retry_policy=retry_policy,
            approval_gate=approval_gate,
            repair_repository=repair_repository,
            incident_repository=incident_repository,
            execution_repository=execution_repository,
        )

    return create_sentinel_graph(
        planner_agent,
        investigator_agent,
    )
