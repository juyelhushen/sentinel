from dataclasses import dataclass
from enum import Enum


class PlanStepType(str, Enum):
    """Types of investigation steps."""

    INSPECT_FILE = "inspect_file"
    SEARCH_CODE = "search_code"
    RUN_TESTS = "run_tests"
    ANALYZE_LOGS = "analyze_logs"


@dataclass(frozen=True)
class PlanStep:
    """A single step in an investigation plan."""

    step_number: int
    action: PlanStepType
    description: str


@dataclass(frozen=True)
class InvestigationPlan:
    """A structured plan for investigating an incident."""

    summary: str
    steps: tuple[PlanStep, ...]