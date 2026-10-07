from typing import TypedDict

from sentinel.agents.investigator.models import InvestigationResult
from sentinel.agents.planner.models import InvestigationPlan
from sentinel.domain.models.execution import Execution
from sentinel.domain.models.incident import Incident
from sentinel.domain.models.verification import VerificationResult
from sentinel.domain.repair.attempt import RepairAttempt
from sentinel.domain.repair.models import RepairPlan


class SentinelGraphState(TypedDict, total=False):
    """State shared between Sentinel LangGraph nodes."""

    incident: Incident
    execution: Execution | None
    
    plan: InvestigationPlan | None
    investigation: InvestigationResult | None
    
    repair_plan: RepairPlan | None
    repair_attempts: tuple[RepairAttempt, ...]
    verification: VerificationResult | None
    
    error: str | None
