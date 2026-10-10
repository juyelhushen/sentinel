from datetime import UTC, datetime
from uuid import UUID, uuid4

from sentinel.application.ports.repair_repository import RepairRepository
from sentinel.domain.models.verification import VerificationResult, VerificationStatus
from sentinel.domain.repair.attempt import RepairAttempt
from sentinel.domain.repair.models import RepairPlan, RepairStep, RepairStepType
from sentinel.infrastructure.database.sqlite import SQLiteDatabase


class SQLiteRepairRepository(RepairRepository):
    """Persists repair attempts, repair steps, and verification results."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    async def save_attempt(
        self,
        execution_id: UUID,
        attempt: RepairAttempt,
    ) -> None:
        """Persist an attempt and all its associated data atomically."""
        created_at = datetime.now(UTC).isoformat()

        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO repair_attempts (
                    id,
                    repair_plan_id,
                    execution_id,
                    attempt_number,
                    plan_summary,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    repair_plan_id = excluded.repair_plan_id,
                    execution_id = excluded.execution_id,
                    attempt_number = excluded.attempt_number,
                    plan_summary = excluded.plan_summary
                """,
                (
                    str(attempt.id),
                    str(attempt.repair_plan.id),
                    str(execution_id),
                    attempt.attempt_number,
                    attempt.repair_plan.summary,
                    created_at,
                ),
            )

            connection.execute(
                """
                DELETE FROM repair_steps
                WHERE repair_attempt_id = ?
                """,
                (str(attempt.id),),
            )

            connection.execute(
                """
                DELETE FROM verifications
                WHERE repair_attempt_id = ?
                """,
                (str(attempt.id),),
            )

            for step in attempt.repair_plan.steps:
                connection.execute(
                    """
                    INSERT INTO repair_steps (
                        id,
                        repair_attempt_id,
                        step_number,
                        action,
                        file_path,
                        description,
                        patch
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        str(attempt.id),
                        step.step_number,
                        step.action.value,
                        step.file_path,
                        step.description,
                        step.patch,
                    ),
                )

            verification = attempt.verification

            if verification is not None:
                connection.execute(
                    """
                    INSERT INTO verifications (
                        id,
                        repair_attempt_id,
                        status,
                        summary,
                        test_output,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(verification.id),
                        str(attempt.id),
                        verification.status.value,
                        verification.summary,
                        verification.test_output,
                        created_at,
                    ),
                )

    async def get_attempts(
        self,
        execution_id: UUID,
    ) -> list[RepairAttempt]:
        """Retrieve an execution's repair history in attempt order."""
        with self._database.connect() as connection:
            connection.row_factory = __import__("sqlite3").Row

            attempt_rows = connection.execute(
                """
                SELECT id, repair_plan_id, attempt_number, plan_summary
                FROM repair_attempts
                WHERE execution_id = ?
                ORDER BY attempt_number ASC
                """,
                (str(execution_id),),
            ).fetchall()

            attempts: list[RepairAttempt] = []

            for attempt_row in attempt_rows:
                attempt_id = UUID(attempt_row["id"])

                step_rows = connection.execute(
                    """
                    SELECT
                        step_number,
                        action,
                        file_path,
                        description,
                        patch
                    FROM repair_steps
                    WHERE repair_attempt_id = ?
                    ORDER BY step_number ASC
                    """,
                    (str(attempt_id),),
                ).fetchall()

                steps = tuple(
                    RepairStep(
                        step_number=row["step_number"],
                        action=RepairStepType(row["action"]),
                        file_path=row["file_path"],
                        description=row["description"],
                        patch=row["patch"],
                    )
                    for row in step_rows
                )

                plan_id = UUID(attempt_row["repair_plan_id"])
                plan = RepairPlan(
                    id=plan_id,
                    summary=attempt_row["plan_summary"],
                    steps=steps,
                )

                verification_row = connection.execute(
                    """
                    SELECT id, status, summary, test_output
                    FROM verifications
                    WHERE repair_attempt_id = ?
                    ORDER BY created_at DESC, rowid DESC
                    LIMIT 1
                    """,
                    (str(attempt_id),),
                ).fetchone()

                verification = None

                if verification_row is not None:
                    verification = VerificationResult(
                        id=UUID(verification_row["id"]),
                        status=VerificationStatus(
                            verification_row["status"]
                        ),
                        summary=verification_row["summary"],
                        test_output=verification_row["test_output"],
                    )

                attempts.append(
                    RepairAttempt(
                        id=attempt_id,
                        attempt_number=attempt_row["attempt_number"],
                        repair_plan=plan,
                        verification=verification,
                    )
                )

            return attempts

    @staticmethod
    def _get_plan_summary(
        connection,
        attempt_id: UUID,
        steps: tuple[RepairStep, ...],
    ) -> str:
        """Read the plan summary stored with the attempt."""
        row = connection.execute(
            """
            SELECT plan_summary
            FROM repair_attempts
            WHERE id = ?
            """,
            (str(attempt_id),),
        ).fetchone()

        if row is None:
            raise ValueError(f"Repair attempt not found: {attempt_id}")

        return row["plan_summary"]