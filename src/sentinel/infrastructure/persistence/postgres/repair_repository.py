from datetime import UTC, datetime
from uuid import UUID, uuid4

from sentinel.application.ports.repair_repository import RepairRepository
from sentinel.domain.models.verification import VerificationResult, VerificationStatus
from sentinel.domain.repair.approval import RepairApproval, RepairApprovalStatus
from sentinel.domain.repair.attempt import RepairAttempt
from sentinel.domain.repair.models import RepairPlan, RepairStep, RepairStepType
from sentinel.infrastructure.database.postgres import (
    PostgreSQLDatabase,
    postgres_transaction,
)


class PostgreSQLRepairRepository(RepairRepository):
    def __init__(self, database: PostgreSQLDatabase) -> None:
        self._database = database

    async def save_attempt(self, execution_id: UUID, attempt: RepairAttempt) -> None:
        created_at = datetime.now(UTC)
        async with postgres_transaction(self._database) as connection:
            await connection.execute(
                """
                INSERT INTO repair_attempts (
                    id, repair_plan_id, execution_id, attempt_number, plan_summary,
                    approval_status, approval_reason, execution_error, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    repair_plan_id = EXCLUDED.repair_plan_id,
                    execution_id = EXCLUDED.execution_id,
                    attempt_number = EXCLUDED.attempt_number,
                    plan_summary = EXCLUDED.plan_summary,
                    approval_status = EXCLUDED.approval_status,
                    approval_reason = EXCLUDED.approval_reason,
                    execution_error = EXCLUDED.execution_error
                """,
                (
                    attempt.id,
                    attempt.repair_plan.id,
                    execution_id,
                    attempt.attempt_number,
                    attempt.repair_plan.summary,
                    attempt.approval.status.value if attempt.approval else None,
                    attempt.approval.reason if attempt.approval else None,
                    attempt.execution_error,
                    created_at,
                ),
            )
            await connection.execute(
                "DELETE FROM repair_steps WHERE repair_attempt_id = %s", (attempt.id,)
            )
            await connection.execute(
                "DELETE FROM verifications WHERE repair_attempt_id = %s", (attempt.id,)
            )
            for step in attempt.repair_plan.steps:
                await connection.execute(
                    """
                    INSERT INTO repair_steps (
                        id, repair_attempt_id, step_number, action, file_path, description, patch
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        uuid4(),
                        attempt.id,
                        step.step_number,
                        step.action.value,
                        step.file_path,
                        step.description,
                        step.patch,
                    ),
                )
            verification = attempt.verification
            if verification is not None:
                await connection.execute(
                    """
                    INSERT INTO verifications (
                        id, repair_attempt_id, status, summary, test_output, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        verification.id,
                        attempt.id,
                        verification.status.value,
                        verification.summary,
                        verification.test_output,
                        created_at,
                    ),
                )

    async def get_attempts(self, execution_id: UUID) -> list[RepairAttempt]:
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                "SELECT * FROM repair_attempts WHERE execution_id = %s ORDER BY attempt_number ASC",
                (execution_id,),
            )
            attempts: list[RepairAttempt] = []
            for row in await cursor.fetchall():
                step_cursor = await connection.execute(
                    "SELECT * FROM repair_steps WHERE repair_attempt_id = %s ORDER BY step_number ASC",
                    (row["id"],),
                )
                steps = tuple(
                    RepairStep(
                        step_number=step["step_number"],
                        action=RepairStepType(step["action"]),
                        file_path=step["file_path"],
                        description=step["description"],
                        patch=step["patch"],
                    )
                    for step in await step_cursor.fetchall()
                )
                verification_cursor = await connection.execute(
                    """
                    SELECT * FROM verifications WHERE repair_attempt_id = %s
                    ORDER BY created_at DESC, id DESC LIMIT 1
                    """,
                    (row["id"],),
                )
                verification_row = await verification_cursor.fetchone()
                verification = None
                if verification_row is not None:
                    verification = VerificationResult(
                        id=verification_row["id"],
                        status=VerificationStatus(verification_row["status"]),
                        summary=verification_row["summary"],
                        test_output=verification_row["test_output"],
                    )
                attempts.append(
                    RepairAttempt(
                        id=row["id"],
                        attempt_number=row["attempt_number"],
                        repair_plan=RepairPlan(
                            id=row["repair_plan_id"],
                            summary=row["plan_summary"],
                            steps=steps,
                        ),
                        verification=verification,
                        approval=(
                            RepairApproval(
                                status=RepairApprovalStatus(row["approval_status"]),
                                reason=row["approval_reason"] or "",
                            )
                            if row["approval_status"] is not None
                            else None
                        ),
                        execution_error=row["execution_error"],
                    )
                )
        return attempts
