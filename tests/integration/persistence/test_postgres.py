import asyncio
import hashlib
import os
from collections.abc import AsyncIterator
from dataclasses import replace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from psycopg import errors, sql

from sentinel.bootstrap.investigation import create_investigation_service
from sentinel.bootstrap.persistence import create_persistence
from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.enums.incident_status import IncidentStatus
from sentinel.domain.models.execution import Execution
from sentinel.domain.models.incident import Incident
from sentinel.domain.models.verification import VerificationResult, VerificationStatus
from sentinel.domain.repair.approval import RepairApproval, RepairApprovalStatus
from sentinel.domain.repair.attempt import RepairAttempt
from sentinel.domain.repair.models import RepairPlan, RepairStep, RepairStepType
from sentinel.domain.tool_execution import ToolExecution
from sentinel.infrastructure.database.postgres import PostgreSQLDatabase
from sentinel.infrastructure.database.postgres_schema import initialize_postgres_schema
from sentinel.infrastructure.persistence.postgres.execution_repository import (
    PostgreSQLExecutionRepository,
)
from sentinel.infrastructure.persistence.postgres.incident_repository import (
    PostgreSQLIncidentRepository,
)
from sentinel.infrastructure.persistence.postgres.rate_limiter import (
    PostgreSQLRateLimitStore,
)
from sentinel.infrastructure.persistence.postgres.repair_repository import (
    PostgreSQLRepairRepository,
)
from sentinel.infrastructure.persistence.postgres.tool_execution_repository import (
    PostgreSQLToolExecutionRepository,
)
from sentinel.llm.base import LLMProvider
from sentinel.llm.models import LLMResponse
from sentinel.tools.models import ToolExecutionStatus
from tests.fixtures.postgres import validate_test_target

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def database() -> AsyncIterator[PostgreSQLDatabase]:
    test_url = os.environ.get("TEST_POSTGRES_URL")
    if not test_url:
        pytest.skip(
            "TEST_POSTGRES_URL is not configured; no PostgreSQL network calls made."
        )
    validate_test_target(test_url)
    schema = f"sentinel_test_{uuid4().hex}"
    database = PostgreSQLDatabase(test_url, schema=schema, timeout_seconds=5)
    try:
        await database.open()
        await asyncio.gather(
            initialize_postgres_schema(database), initialize_postgres_schema(database)
        )
        yield database
    finally:
        try:
            async with database.connection(select_schema=False) as connection:
                await connection.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema)
                    )
                )
        finally:
            await database.close()


async def test_incident_execution_and_audit_round_trip(
    database: PostgreSQLDatabase,
) -> None:
    incidents = PostgreSQLIncidentRepository(database)
    executions = PostgreSQLExecutionRepository(database)
    audits = PostgreSQLToolExecutionRepository(database)
    incident = Incident(title="Failure", description="Tests failed", repository="test")
    await incidents.save(incident)
    restored = await incidents.get_by_id(incident.id)
    assert restored is not None
    assert restored.id == incident.id
    assert restored.created_at == incident.created_at
    assert restored.status == incident.status
    assert await incidents.get(uuid4()) is None
    incident.start_investigation()
    await incidents.persist(incident)
    assert (await incidents.get(incident.id)).status == incident.status

    execution = Execution(incident_id=incident.id)
    await executions.save(execution)
    execution.start()
    execution.complete()
    await executions.save(execution)
    assert await executions.get_by_id(execution.id) == execution
    assert await executions.get_by_incident_id(incident.id) == [execution]
    assert await executions.get_by_id(uuid4()) is None

    pending = Execution(incident_id=incident.id)
    await executions.save(pending)
    assert await executions.get_by_incident_id(incident.id) == [pending, execution]

    record = ToolExecution(
        tool_name="read_file",
        status=ToolExecutionStatus.SUCCESS,
        execution_id=execution.id,
        arguments={"path": "file.txt", "nested": [1, None, True]},
        output="contents",
    )
    await audits.save(record)
    assert await audits.get_by_execution_id(execution.id) == [record]
    with pytest.raises(errors.UniqueViolation):
        await audits.save(record)
    assert await audits.get_by_execution_id(execution.id) == [record]


async def test_foreign_keys_and_transaction_rollback(
    database: PostgreSQLDatabase,
) -> None:
    incidents = PostgreSQLIncidentRepository(database)
    executions = PostgreSQLExecutionRepository(database)
    with pytest.raises(errors.ForeignKeyViolation):
        await executions.save(Execution(incident_id=uuid4()))
    incident = Incident(title="Failure", description="Tests failed", repository="test")
    execution = Execution(incident_id=incident.id)
    with pytest.raises(RuntimeError, match="rollback"):
        async with database.connection() as connection:
            await incidents.save(incident, connection)
            await executions.save(execution, connection)
            raise RuntimeError("rollback")
    assert await incidents.get(incident.id) is None
    assert await executions.get_by_id(execution.id) is None
    async with database.connection() as connection:
        await incidents.save(incident, connection)
        await executions.save(execution, connection)
    assert await executions.get_by_id(execution.id) == execution
    async with database.connection() as connection:
        await connection.execute("DELETE FROM incidents WHERE id = %s", (incident.id,))
    assert await executions.get_by_id(execution.id) is None


async def test_repeated_and_concurrent_schema_initialization_preserves_data(
    database: PostgreSQLDatabase,
) -> None:
    repository = PostgreSQLIncidentRepository(database)
    incident = Incident(title="Failure", description="Tests failed", repository="test")
    await repository.save(incident)
    await asyncio.gather(
        initialize_postgres_schema(database), initialize_postgres_schema(database)
    )
    assert (await repository.get(incident.id)).id == incident.id
    async with database.connection() as connection:
        cursor = await connection.execute("SELECT version FROM schema_migrations")
        assert await cursor.fetchall() == [{"version": 1}, {"version": 2}]


async def test_distributed_rate_limit_is_atomic_across_store_instances(
    database: PostgreSQLDatabase,
) -> None:
    first = PostgreSQLRateLimitStore(database)
    second = PostgreSQLRateLimitStore(database)
    raw_key = "integration-private-api-key"

    async def attempt(index: int) -> bool:
        store = first if index % 2 == 0 else second
        return await store.check_and_record(raw_key, "POST:/incidents", 5, 60) is None

    allowed = await asyncio.gather(*(attempt(index) for index in range(20)))

    assert sum(allowed) == 5
    async with database.connection() as connection:
        cursor = await connection.execute(
            "SELECT api_key_hash FROM rate_limit_requests "
            "WHERE endpoint = %s ORDER BY requested_at",
            ("POST:/incidents",),
        )
        rows = await cursor.fetchall()
    expected_hash = hashlib.sha256(raw_key.encode()).digest()
    assert len(rows) == 5
    assert all(row["api_key_hash"] == expected_hash for row in rows)
    assert all(raw_key.encode() not in row["api_key_hash"] for row in rows)


async def test_rate_limit_buckets_are_isolated_and_expired_rows_are_cleaned(
    database: PostgreSQLDatabase,
) -> None:
    store = PostgreSQLRateLimitStore(database)
    key = "isolated-private-api-key"

    assert await store.check_and_record(key, "GET:/health", 1, 60) is None
    assert await store.check_and_record(key, "GET:/health", 1, 60) is not None
    assert await store.check_and_record("other-key", "GET:/health", 1, 60) is None
    assert await store.check_and_record(key, "POST:/incidents", 1, 60) is None

    expired_key = hashlib.sha256(b"expired-key").digest()
    async with database.connection() as connection:
        await connection.execute(
            """
            INSERT INTO rate_limit_requests (
                api_key_hash, endpoint, requested_at, expires_at
            ) VALUES (
                %s, %s, clock_timestamp() - INTERVAL '2 minutes',
                clock_timestamp() - INTERVAL '1 minute'
            )
            """,
            (expired_key, "GET:/expired"),
        )

    assert await store.check_and_record("cleanup-trigger", "GET:/health", 5) is None
    async with database.connection() as connection:
        cursor = await connection.execute(
            "SELECT COUNT(*) AS request_count FROM rate_limit_requests "
            "WHERE api_key_hash = %s AND endpoint = %s",
            (expired_key, "GET:/expired"),
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row["request_count"] == 0


async def test_repair_attempts_steps_verifications_and_atomic_update(
    database: PostgreSQLDatabase,
) -> None:
    incident = Incident(title="Failure", description="Tests failed", repository="test")
    execution = Execution(incident_id=incident.id)
    await PostgreSQLIncidentRepository(database).save(incident)
    await PostgreSQLExecutionRepository(database).save(execution)
    repository = PostgreSQLRepairRepository(database)
    attempt = RepairAttempt(
        attempt_number=1,
        repair_plan=RepairPlan(
            summary="Fix",
            steps=(
                RepairStep(
                    step_number=1,
                    action=RepairStepType.APPLY_PATCH,
                    file_path="file.py",
                    description="Fix code",
                    patch="test patch",
                ),
            ),
        ),
        approval=RepairApproval(RepairApprovalStatus.APPROVED, "test approval"),
        verification=VerificationResult(
            VerificationStatus.PASSED, "Passed", "1 passed"
        ),
    )
    await repository.save_attempt(execution.id, attempt)
    await repository.save_attempt(execution.id, attempt)
    assert await repository.get_attempts(execution.id) == [attempt]
    with pytest.raises(errors.UniqueViolation):
        await repository.save_attempt(execution.id, replace(attempt, id=uuid4()))
    with pytest.raises(errors.ForeignKeyViolation):
        await repository.save_attempt(uuid4(), replace(attempt, id=uuid4()))
    invalid_step = replace(attempt.repair_plan.steps[0], patch=None)
    invalid = replace(
        attempt, repair_plan=replace(attempt.repair_plan, steps=(invalid_step,))
    )
    with pytest.raises(errors.NotNullViolation):
        await repository.save_attempt(execution.id, invalid)
    assert await repository.get_attempts(execution.id) == [attempt]
    second = replace(
        attempt,
        id=uuid4(),
        attempt_number=2,
        verification=None,
        execution_error="failed",
    )
    await repository.save_attempt(execution.id, second)
    assert await repository.get_attempts(execution.id) == [attempt, second]


async def test_investigation_factory_uses_real_postgres_without_enabling_repair(
    database: PostgreSQLDatabase,
    tmp_path,
) -> None:
    persistence = create_persistence(database)
    incident = Incident(title="Failure", description="Tests failed", repository="test")
    await persistence.incidents.persist(incident)
    provider = AsyncMock(spec=LLMProvider)
    provider.generate.return_value = LLMResponse(
        content='{"summary": "Investigation complete", "steps": []}', model="test"
    )
    service = create_investigation_service(
        llm_provider=provider, repository_root=tmp_path, persistence=persistence
    )

    result = await service.investigate(incident.id)

    assert result["error"] is None
    assert result.get("repair_enabled") is False
    execution = result["execution"]
    assert execution is not None
    assert execution.status == ExecutionStatus.COMPLETED
    assert await persistence.executions.get_by_id(execution.id) == execution
    restored = await persistence.incidents.get_by_id(incident.id)
    assert restored is not None
    assert restored.status == IncidentStatus.VERIFYING
    assert await persistence.repairs.get_attempts(execution.id) == []
    provider.generate.assert_awaited_once()
