from typing import TypedDict

from sentinel.agents.planner.models import InvestigationPlan
from sentinel.domain.models.incident import Incident


class SentinelGraphState(TypedDict):
    """State shared between Sentinel LangGraph nodes."""

    incident: Incident
    plan: InvestigationPlan | None
    error: str | None