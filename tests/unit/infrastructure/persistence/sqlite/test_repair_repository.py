import sqlite3
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from sentinel.domain.models.verification import VerificationResult, VerificationStatus
from sentinel.domain.repair import (
    RepairAttempt,
    RepairPlan,
    RepairStep,
    RepairStepType,
)
from sentinel.infrastructure.database.sqlite import SQLiteDatabase
from sentinel.infrastructure.persistence.sqllite.repair_repository import (
    SQLiteRepairRepository,
)


def create_test_database(database_path: Path) -> SQLiteDatabase:
    """Create an isolated database using the repair persistence schema."""
    database = SQLiteDatabase(database_path)

    with database.connect() as connection:
        connection.executescript(
            """
            CREATE TABLE incidents (
                id TEXT PRIMARY KEY
            );

            CREATE TABLE executions (
                id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                FOREIGN KEY (incident_id)
                    REFERENCES incidents(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE repair_attempts (
                id TEXT PRIMARY KEY,
                repair_plan_id TEXT NOT NULL,
                execution_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                plan_summary TEXT NOT NULL,
                approval_status TEXT,
                approval_reason TEXT,
                execution_error TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (execution_id)
                    REFERENCES executions(id)
                    ON DELETE CASCADE,
                UNIQUE (execution_id, attempt_number)
            );

            CREATE TABLE repair_steps (
                id TEXT PRIMARY KEY,
                repair_attempt_id TEXT NOT NULL,
                step_number INTEGER NOT NULL,
                action TEXT NOT NULL,
                file_path TEXT NOT NULL,
                description TEXT NOT NULL,
                patch TEXT NOT NULL,
                FOREIGN KEY (repair_attempt_id)
                    REFERENCES repair_attempts(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE verifications (
                id TEXT PRIMARY KEY,
                repair_attempt_id TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT NOT NULL,
                test_output TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (repair_attempt_id)
                    REFERENCES repair_attempts(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX idx_repair_attempts_execution_id
                ON repair_attempts(execution_id);

            CREATE INDEX idx_repair_steps_attempt_id
                ON repair_steps(repair_attempt_id);

            CREATE INDEX idx_verifications_attempt_id
                ON verifications(repair_attempt_id);
            """
        )

    return database


def create_execution(database: SQLiteDatabase) -> UUID:
    """Insert the parent records required by the foreign keys."""
    incident_id = uuid4()
    execution_id = uuid4()

    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO incidents (id) VALUES (?)",
            (str(incident_id),),
        )
        connection.execute(
            """
            INSERT INTO executions (id, incident_id)
            VALUES (?, ?)
            """,
            (str(execution_id), str(incident_id)),
        )

    return execution_id


def create_attempt(
    attempt_number: int = 1,
    with_verification: bool = True,
) -> RepairAttempt:
    step = RepairStep(
        step_number=1,
        action=RepairStepType.APPLY_PATCH,
        file_path="src/service.py",
        description="Handle missing customer",
        patch=(
            "--- a/src/service.py\n"
            "+++ b/src/service.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-return customer.id\n"
            "+return customer.id if customer else None\n"
        ),
    )

    plan = RepairPlan(
        summary="Fix missing customer handling",
        steps=(step,),
    )

    verification = None

    if with_verification:
        verification = VerificationResult(
            status=VerificationStatus.PASSED,
            summary="Verification tests passed.",
            test_output="5 passed in 0.12s",
        )

    return RepairAttempt(
        attempt_number=attempt_number,
        repair_plan=plan,
        verification=verification,
    )


@pytest.fixture
def database(tmp_path: Path) -> SQLiteDatabase:
    return create_test_database(tmp_path / "test_sentinel.db")


@pytest.fixture
def repository(database: SQLiteDatabase) -> SQLiteRepairRepository:
    return SQLiteRepairRepository(database)


@pytest.fixture
def execution_id(database: SQLiteDatabase) -> UUID:
    return create_execution(database)


@pytest.mark.asyncio
async def test_save_and_retrieve_attempt(
    repository: SQLiteRepairRepository,
    execution_id: UUID,
) -> None:
    attempt = create_attempt()

    await repository.save_attempt(execution_id, attempt)

    attempts = await repository.get_attempts(execution_id)

    assert len(attempts) == 1

    restored = attempts[0]

    assert restored.id == attempt.id
    assert restored.attempt_number == 1
    assert restored.repair_plan.id == attempt.repair_plan.id
    assert restored.repair_plan.summary == attempt.repair_plan.summary
    assert restored.repair_plan.steps == attempt.repair_plan.steps
    assert restored.verification == attempt.verification


@pytest.mark.asyncio
async def test_save_attempt_without_verification(
    repository: SQLiteRepairRepository,
    execution_id: UUID,
) -> None:
    attempt = create_attempt(with_verification=False)

    await repository.save_attempt(execution_id, attempt)

    attempts = await repository.get_attempts(execution_id)

    assert len(attempts) == 1
    assert attempts[0].verification is None


@pytest.mark.asyncio
async def test_retrieves_attempts_in_attempt_number_order(
    repository: SQLiteRepairRepository,
    execution_id: UUID,
) -> None:
    second = create_attempt(attempt_number=2)
    first = create_attempt(attempt_number=1)

    await repository.save_attempt(execution_id, second)
    await repository.save_attempt(execution_id, first)

    attempts = await repository.get_attempts(execution_id)

    assert [attempt.attempt_number for attempt in attempts] == [1, 2]


@pytest.mark.asyncio
async def test_retrieves_all_repair_steps(
    repository: SQLiteRepairRepository,
    execution_id: UUID,
) -> None:
    first_step = RepairStep(
        step_number=1,
        action=RepairStepType.APPLY_PATCH,
        file_path="src/service.py",
        description="Add a guard",
        patch="patch one",
    )
    second_step = RepairStep(
        step_number=2,
        action=RepairStepType.APPLY_PATCH,
        file_path="src/repository.py",
        description="Fix repository handling",
        patch="patch two",
    )

    attempt = RepairAttempt(
        attempt_number=1,
        repair_plan=RepairPlan(
            summary="Fix service and repository",
            steps=(first_step, second_step),
        ),
    )

    await repository.save_attempt(execution_id, attempt)

    attempts = await repository.get_attempts(execution_id)

    assert len(attempts[0].repair_plan.steps) == 2
    assert attempts[0].repair_plan.steps == (first_step, second_step)


@pytest.mark.asyncio
async def test_attempts_are_scoped_to_execution(
    repository: SQLiteRepairRepository,
    database: SQLiteDatabase,
) -> None:
    first_execution = create_execution(database)
    second_execution = create_execution(database)

    await repository.save_attempt(
        first_execution,
        create_attempt(),
    )

    assert await repository.get_attempts(second_execution) == []


@pytest.mark.asyncio
async def test_save_attempt_is_idempotent(
    repository: SQLiteRepairRepository,
    execution_id: UUID,
    database: SQLiteDatabase,
) -> None:
    attempt = create_attempt()

    await repository.save_attempt(execution_id, attempt)
    await repository.save_attempt(execution_id, attempt)

    attempts = await repository.get_attempts(execution_id)

    assert len(attempts) == 1
    assert attempts[0].id == attempt.id

    with database.connect() as connection:
        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM repair_steps
            WHERE repair_attempt_id = ?
            """,
            (str(attempt.id),),
        ).fetchone()[0]

    assert count == 1


@pytest.mark.asyncio
async def test_cascade_delete_removes_repair_history(
    repository: SQLiteRepairRepository,
    execution_id: UUID,
    database: SQLiteDatabase,
) -> None:
    attempt = create_attempt()

    await repository.save_attempt(execution_id, attempt)

    with database.transaction() as connection:
        connection.execute(
            "DELETE FROM executions WHERE id = ?",
            (str(execution_id),),
        )

    assert await repository.get_attempts(execution_id) == []

    with database.connect() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM repair_attempts").fetchone()[0]
            == 0
        )

        assert (
            connection.execute("SELECT COUNT(*) FROM repair_steps").fetchone()[0] == 0
        )

        assert (
            connection.execute("SELECT COUNT(*) FROM verifications").fetchone()[0] == 0
        )


@pytest.mark.asyncio
async def test_failed_save_rolls_back_all_changes(
    repository: SQLiteRepairRepository,
    execution_id: UUID,
    database: SQLiteDatabase,
) -> None:
    attempt = create_attempt()

    # Force a failure when the repository tries to insert repair steps.
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_repair_step
            BEFORE INSERT ON repair_steps
            BEGIN
                SELECT RAISE(ABORT, 'simulated persistence failure');
            END;
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        await repository.save_attempt(execution_id, attempt)

    assert await repository.get_attempts(execution_id) == []

    with database.connect() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM repair_attempts").fetchone()[0]
            == 0
        )
