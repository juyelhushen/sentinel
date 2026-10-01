from uuid import UUID

import pytest

from sentinel.domain.repair import (
    RepairPlan,
    RepairStep,
    RepairStepType,
)


def test_repair_step_can_be_created() -> None:
    step = RepairStep(
        step_number=1,
        action=RepairStepType.APPLY_PATCH,
        file_path="src/order/service.py",
        description="Handle missing customer before accessing customer.id",
        patch="@@ -10,1 +10,2 @@",
    )

    assert step.step_number == 1
    assert step.action == RepairStepType.APPLY_PATCH
    assert step.file_path == "src/order/service.py"


def test_repair_plan_generates_id() -> None:
    step = RepairStep(
        step_number=1,
        action=RepairStepType.APPLY_PATCH,
        file_path="src/order/service.py",
        description="Fix null handling",
        patch="patch",
    )

    plan = RepairPlan(
        summary="Fix order service null handling",
        steps=(step,),
    )

    assert isinstance(plan.id, UUID)
    assert plan.summary == "Fix order service null handling"
    assert len(plan.steps) == 1


def test_repair_step_is_immutable() -> None:
    step = RepairStep(
        step_number=1,
        action=RepairStepType.APPLY_PATCH,
        file_path="src/order/service.py",
        description="Fix null handling",
        patch="patch",
    )

    with pytest.raises(AttributeError):
        step.file_path = "other.py"  # type: ignore[misc]