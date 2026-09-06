from dataclasses import dataclass
from typing import Optional

from sentinel.agents.planner.models import InvestigationPlan
from sentinel.domain.models.incident import Incident


@dataclass
class SentinelState:
    """State shared across the Sentinel agent workflow."""

    incident: Incident
    plan: Optional[InvestigationPlan] = None
    error: Optional[str] = None