from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4


class RepairStepType(StrEnum):
    APPLY_PATCH = "apply_patch"

@dataclass(frozen=True)
class RepairStep:
    step_number: int
    action: RepairStepType
    file_path: str
    description: str
    patch: str


@dataclass(frozen=True)
class RepairPlan:
    summary: str
    steps: tuple[RepairStep, ...]
    id: UUID = field(default_factory=uuid4)