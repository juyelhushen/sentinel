from dataclasses import dataclass

from sentinel.agents.planner.models import InvestigationPlan
from sentinel.domain.models.incident import Incident


@dataclass
class SentinelState:
    """State shared across the Sentinel agent workflow."""

    incident: Incident
    plan: InvestigationPlan | None = None
    error: str | None = None
