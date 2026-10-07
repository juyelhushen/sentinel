from sentinel.domain.repair.attempt import RepairAttempt
from sentinel.domain.repair.models import RepairPlan, RepairStep, RepairStepType


def test_repair_attempt_records_plan() -> None:
    plan = RepairPlan(
        summary="Fix null handling",
        steps=(
            RepairStep(
                step_number=1,
                action=RepairStepType.APPLY_PATCH,
                file_path="src/service.py",
                description="Add null check",
                patch="patch",
            ),
        ),
    )

    attempt = RepairAttempt(
        attempt_number=1,
        repair_plan=plan,
    )

    assert attempt.attempt_number == 1
    assert attempt.repair_plan == plan
    assert attempt.verification is None