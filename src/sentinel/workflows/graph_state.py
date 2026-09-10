from typing import TypedDict

from sentinel.agents.investigator.models import InvestigationResult
from sentinel.agents.planner.models import InvestigationPlan
from sentinel.domain.models.execution import Execution
from sentinel.domain.models.incident import Incident


class SentinelGraphState(TypedDict):
    """State shared between Sentinel LangGraph nodes."""

    incident: Incident
    execution: Execution | None
    plan: InvestigationPlan | None
    investigation: InvestigationResult | None
    error: str | None