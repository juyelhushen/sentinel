import json
from pathlib import Path

import pytest

from sentinel.application.ports.repair_approval_gate import RepairApprovalGate
from sentinel.application.ports.repair_repository import RepairRepository
from sentinel.bootstrap.application import create_sentinel_application
from sentinel.domain.enums.execution_status import ExecutionStatus
from sentinel.domain.enums.incident_status import IncidentStatus
from sentinel.domain.models.incident import Incident
from sentinel.domain.repair.approval import (
    RepairApproval,
    RepairApprovalStatus,
)
from sentinel.domain.repair.attempt import RepairAttempt
from sentinel.domain.repair.retry import RepairRetryPolicy
from sentinel.infrastructure.database.schema import SchemaInitializer
from sentinel.infrastructure.database.sqlite import SQLiteDatabase
from sentinel.infrastructure.persistence.sqllite.execution_repository import (
    SQLiteExecutionRepository,
)
from sentinel.infrastructure.persistence.sqllite.incident_repository import (
    SQLiteIncidentRepository,
)
from sentinel.infrastructure.persistence.sqllite.repair_repository import (
    SQLiteRepairRepository,
)
from sentinel.llm.base import LLMProvider
from sentinel.llm.models import LLMRequest, LLMResponse

PLANNER_RESPONSE = json.dumps(
    {
        "summary": "Inspect the broken calculator and reproduce the failure.",
        "steps": [
            {
                "step_number": 1,
                "action": "inspect_file",
                "description": "Inspect calculator implementation.",
                "arguments": {"path": "calculator.py"},
            },
            {
                "step_number": 2,
                "action": "run_tests",
                "description": "Reproduce the failing calculator test.",
                "arguments": {"test_path": "tests"},
            },
        ],
    }
)


class DeterministicLLMProvider(LLMProvider):
    def __init__(self, repair_responses: list[dict]) -> None:
        self._repair_responses = repair_responses
        self.repair_requests: list[LLMRequest] = []
        self.planner_requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        system_prompt = _message_content(request.messages[0])
        if "planning agent" in system_prompt:
            self.planner_requests.append(request)
            content = PLANNER_RESPONSE
        elif "autonomous code repair agent" in system_prompt:
            self.repair_requests.append(request)
            index = len(self.repair_requests) - 1
            if index >= len(self._repair_responses):
                previous_feedback = _message_content(request.messages[-1])
                raise AssertionError(
                    "No deterministic repair response configured. "
                    f"Previous attempt context:\n{previous_feedback}"
                )
            content = json.dumps(self._repair_responses[index])
        else:
            raise AssertionError(f"Unexpected LLM prompt: {system_prompt[:80]}")

        return LLMResponse(content=content, model="deterministic-test-model")

    async def health_check(self) -> bool:
        return True


class FixedApprovalGate(RepairApprovalGate):
    def __init__(self, approval: RepairApproval) -> None:
        self.approval = approval
        self.calls = 0

    async def approve(self, repair_plan) -> RepairApproval:
        self.calls += 1
        return self.approval


class FailingRepairRepository(RepairRepository):
    async def save_attempt(self, execution_id, attempt: RepairAttempt) -> None:
        raise RuntimeError("controlled repair persistence failure")

    async def get_attempts(self, execution_id) -> list[RepairAttempt]:
        return []


def _message_content(message) -> str:
    if isinstance(message, dict):
        return message["content"]
    return message.content


def _repair_response(summary: str, before: str, after: str) -> dict:
    patch = (
        "--- a/calculator.py\n"
        "+++ b/calculator.py\n"
        "@@ -2,1 +2,1 @@\n"
        f"-{before}\n"
        f"+{after}\n"
    )
    return {
        "summary": summary,
        "steps": [
            {
                "step_number": 1,
                "action": "apply_patch",
                "file_path": "calculator.py",
                "description": summary,
                "patch": patch,
            }
        ],
    }


@pytest.fixture
def sample_repository(tmp_path: Path) -> Path:
    (tmp_path / "calculator.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a - b\n",
        encoding="utf-8",
    )
    tests_path = tmp_path / "tests"
    tests_path.mkdir()
    (tests_path / "test_calculator.py").write_text(
        "from calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def database(tmp_path: Path) -> SQLiteDatabase:
    database = SQLiteDatabase(tmp_path / "sentinel-test.sqlite")
    SchemaInitializer(database).initialize()
    return database


def _application(
    repository_root: Path,
    database: SQLiteDatabase,
    repairs: list[dict],
    *,
    approval_gate: RepairApprovalGate | None = None,
    repair_repository: RepairRepository | None = None,
    max_attempts: int = 3,
):
    provider = DeterministicLLMProvider(repairs)
    application = create_sentinel_application(
        llm_provider=provider,
        repository_root=repository_root,
        enable_repair=True,
        verification_path="tests",
        retry_policy=RepairRetryPolicy(max_attempts=max_attempts),
        approval_gate=approval_gate,
        database=database,
        repair_repository=repair_repository,
    )
    return application, provider


def _incident() -> Incident:
    return Incident(
        title="Calculator addition test fails",
        description="The add function returns subtraction results.",
        repository="temporary-calculator",
    )


async def _tool_names(database: SQLiteDatabase) -> list[str]:
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT tool_name FROM tool_executions ORDER BY rowid"
        ).fetchall()
    return [row[0] for row in rows]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_autonomous_repair_fixes_broken_repository(
    sample_repository: Path,
    database: SQLiteDatabase,
) -> None:
    application, provider = _application(
        sample_repository,
        database,
        [_repair_response("Correct addition", "    return a - b", "    return a + b")],
    )
    incident = _incident()

    result = await application.ainvoke({"incident": incident})

    attempts = await SQLiteRepairRepository(database).get_attempts(
        result["execution"].id
    )
    persisted_incident = await SQLiteIncidentRepository(database).get(incident.id)
    persisted_execution = await SQLiteExecutionRepository(database).get_by_id(
        result["execution"].id
    )
    tool_names = await _tool_names(database)

    assert persisted_incident is not None
    assert persisted_execution is not None
    assert provider.planner_requests
    assert len(provider.repair_requests) == 1
    assert result["plan"].steps
    assert result["investigation"].step_results[0].success
    assert result["repair_plan"].steps[0].file_path == "calculator.py"
    assert result["approval"].approved
    assert result["verification"].passed
    assert result["error"] is None
    assert result["execution"].status == ExecutionStatus.COMPLETED
    assert incident.status == IncidentStatus.COMPLETED
    assert persisted_incident.status == IncidentStatus.COMPLETED
    assert persisted_execution.status == ExecutionStatus.COMPLETED
    assert len(attempts) == 1
    assert attempts[0].attempt_number == 1
    assert attempts[0].repair_plan.steps
    assert attempts[0].verification is not None
    assert attempts[0].verification.passed
    assert tool_names.count("apply_patch") == 1
    assert "return a + b" in (sample_repository / "calculator.py").read_text(
        encoding="utf-8"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_autonomous_repair_retries_after_failed_verification(
    sample_repository: Path,
    database: SQLiteDatabase,
) -> None:
    application, provider = _application(
        sample_repository,
        database,
        [
            _repair_response(
                "First attempt leaves the result incorrect",
                "    return a - b",
                "    return a",
            ),
            _repair_response(
                "Use addition instead of returning one operand",
                "    return a",
                "    return a + b",
            ),
        ],
    )
    incident = _incident()

    result = await application.ainvoke({"incident": incident})

    attempts = await SQLiteRepairRepository(database).get_attempts(
        result["execution"].id
    )
    retry_prompt = "\n".join(
        _message_content(message) for message in provider.repair_requests[1].messages
    )

    assert len(attempts) == 2
    assert [attempt.attempt_number for attempt in attempts] == [1, 2]
    assert attempts[0].verification is not None
    assert attempts[1].verification is not None
    assert attempts[0].verification.status.value == "failed"
    assert attempts[1].verification.passed
    assert attempts[0].repair_plan.summary != attempts[1].repair_plan.summary
    assert "First attempt leaves the result incorrect" in retry_prompt
    assert "Verification tests failed" in retry_prompt
    assert "1 failed" in retry_prompt
    assert len(provider.repair_requests) == 2
    assert result["verification"].passed
    assert result["execution"].status == ExecutionStatus.COMPLETED
    assert incident.status == IncidentStatus.COMPLETED
    assert "return a + b" in (sample_repository / "calculator.py").read_text(
        encoding="utf-8"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rejected_repair_does_not_modify_repository(
    sample_repository: Path,
    database: SQLiteDatabase,
) -> None:
    original = (sample_repository / "calculator.py").read_text(encoding="utf-8")
    approval_gate = FixedApprovalGate(
        RepairApproval(RepairApprovalStatus.REJECTED, "Rejected by test policy.")
    )
    application, _ = _application(
        sample_repository,
        database,
        [_repair_response("Unapproved change", "    return a - b", "    return a + b")],
        approval_gate=approval_gate,
    )
    incident = _incident()

    result = await application.ainvoke({"incident": incident})

    attempts = await SQLiteRepairRepository(database).get_attempts(
        result["execution"].id
    )
    tool_names = await _tool_names(database)

    assert result["repair_plan"].steps
    assert approval_gate.calls == 1
    assert result["approval"].status == RepairApprovalStatus.REJECTED
    assert result["verification"] is None
    assert "Rejected by test policy" in result["error"]
    assert result["execution"].status == ExecutionStatus.FAILED
    assert incident.status == IncidentStatus.FAILED
    assert len(attempts) == 1
    assert attempts[0].approval is not None
    assert attempts[0].approval.status == RepairApprovalStatus.REJECTED
    assert attempts[0].verification is None
    assert attempts[0].execution_error == "Rejected by test policy."
    assert "apply_patch" not in tool_names
    assert (sample_repository / "calculator.py").read_text(encoding="utf-8") == original


@pytest.mark.integration
@pytest.mark.asyncio
async def test_autonomous_repair_stops_after_retry_limit(
    sample_repository: Path,
    database: SQLiteDatabase,
) -> None:
    application, provider = _application(
        sample_repository,
        database,
        [
            _repair_response(
                "Return only the first operand", "    return a - b", "    return a"
            ),
            _repair_response(
                "Return only the second operand", "    return a", "    return b"
            ),
            _repair_response(
                "Restore the incorrect subtraction", "    return b", "    return a - b"
            ),
        ],
        max_attempts=3,
    )
    incident = _incident()

    result = await application.ainvoke({"incident": incident})

    attempts = await SQLiteRepairRepository(database).get_attempts(
        result["execution"].id
    )

    assert len(attempts) == 3
    assert len(provider.repair_requests) == 3
    assert [attempt.attempt_number for attempt in attempts] == [1, 2, 3]
    assert all(attempt.verification is not None for attempt in attempts)
    assert all(
        attempt.verification is not None and not attempt.verification.passed
        for attempt in attempts
    )
    assert result["execution"].status == ExecutionStatus.FAILED
    assert incident.status == IncidentStatus.FAILED
    assert result["error"] is not None
    assert "verification" in result["error"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repair_persistence_failure_is_not_silently_ignored(
    sample_repository: Path,
    database: SQLiteDatabase,
) -> None:
    application, _ = _application(
        sample_repository,
        database,
        [_repair_response("Correct addition", "    return a - b", "    return a + b")],
        repair_repository=FailingRepairRepository(),
    )
    incident = _incident()

    with pytest.raises(RuntimeError, match="controlled repair persistence failure"):
        await application.ainvoke({"incident": incident})

    executions = await SQLiteExecutionRepository(database).get_by_incident_id(
        incident.id
    )

    assert len(executions) == 1
    assert executions[0].status == ExecutionStatus.RUNNING
    assert incident.status != IncidentStatus.COMPLETED
    assert "return a + b" in (sample_repository / "calculator.py").read_text(
        encoding="utf-8"
    )
