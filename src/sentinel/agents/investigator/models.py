from dataclasses import dataclass

from sentinel.agents.planner.models import PlanStepType

@dataclass(frozen=True)
class StepInvestigationResult:
    """Result of investigation a single plan step"""

    step_number: int
    action: PlanStepType
    success: bool
    findings: str

@dataclass(frozen=True)
class InvestigationResult:
    """Result of an investigation"""

    summary: str
    step_results: tuple[StepInvestigationResult, ...]