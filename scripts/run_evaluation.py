from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = Path("data/evaluation-reports")


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    node_id: str
    expected_outcome: str


SCENARIOS = (
    Scenario(
        "investigation_fact_accuracy",
        "tests/integration/workflows/test_autonomous_repair.py::test_investigation_findings_match_calculator_facts_without_repair",
        "facts_confirmed",
    ),
    Scenario(
        "successful_repair_and_persistence",
        "tests/integration/workflows/test_autonomous_repair.py::test_autonomous_repair_fixes_broken_repository",
        "repair_verified_and_persisted",
    ),
    Scenario(
        "invalid_proposal_rejection",
        "tests/integration/workflows/test_autonomous_repair.py::test_invalid_repair_proposal_fails_through_investigation_service",
        "invalid_proposal_safely_rejected",
    ),
    Scenario(
        "verification_retry",
        "tests/integration/workflows/test_autonomous_repair.py::test_autonomous_repair_retries_after_failed_verification",
        "repaired_after_verification_retry",
    ),
    Scenario(
        "retry_exhaustion_and_persisted_failure",
        "tests/integration/workflows/test_autonomous_repair.py::test_autonomous_repair_stops_after_retry_limit",
        "retry_exhausted_and_failure_persisted",
    ),
    Scenario(
        "approval_rejection",
        "tests/integration/workflows/test_autonomous_repair.py::test_rejected_repair_does_not_modify_repository",
        "approval_rejected_without_mutation",
    ),
)

SAFE_ERROR_CATEGORIES = frozenset({"repair_parse_error"})


class EvaluationCollector:
    def __init__(self) -> None:
        self.phase_statuses: dict[str, dict[str, str]] = {}
        self.elapsed_seconds: dict[str, float] = {}
        self.protocol_counts: dict[str, int] = {}
        self.properties: dict[str, dict[str, object]] = {}
        self.error_categories: dict[str, str] = {}

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(
        self,
        item: pytest.Item,
        nextitem: pytest.Item | None,
    ):
        started = perf_counter()
        self.protocol_counts[item.nodeid] = self.protocol_counts.get(item.nodeid, 0) + 1
        try:
            yield
        finally:
            elapsed = perf_counter() - started
            self.elapsed_seconds[item.nodeid] = (
                self.elapsed_seconds.get(item.nodeid, 0.0) + elapsed
            )

    @pytest.hookimpl
    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.failed:
            status = "failed"
            self.error_categories[report.nodeid] = {
                "setup": "test_setup_failure",
                "call": "test_call_failure",
                "teardown": "test_teardown_failure",
            }.get(report.when, "test_failure")
        elif report.skipped:
            status = "skipped"
            self.error_categories[report.nodeid] = "scenario_skipped"
        else:
            status = "passed"

        self.phase_statuses.setdefault(report.nodeid, {})[report.when] = status
        if report.when == "call":
            properties = self.properties.setdefault(report.nodeid, {})
            for name, value in report.user_properties:
                if name in {"evaluation_outcome", "retry_count", "error_category"}:
                    properties[name] = value


def _test_status(collector: EvaluationCollector, node_id: str) -> str:
    phases = collector.phase_statuses.get(node_id, {})
    if "failed" in phases.values():
        return "failed"
    if "skipped" in phases.values():
        return "skipped"
    if phases.get("call") == "passed":
        return "passed"
    return "not_collected"


def _scenario_result(
    scenario: Scenario,
    collector: EvaluationCollector,
    *,
    duplicate: bool = False,
) -> dict[str, Any]:
    execution_count = collector.protocol_counts.get(scenario.node_id, 0)
    is_duplicate = duplicate or execution_count > 1
    test_status = (
        "duplicate" if is_duplicate else _test_status(collector, scenario.node_id)
    )
    properties = collector.properties.get(scenario.node_id, {})
    if test_status == "duplicate":
        actual_outcome = "duplicate_result"
    elif test_status == "passed":
        recorded_outcome = properties.get("evaluation_outcome")
        actual_outcome = (
            recorded_outcome
            if isinstance(recorded_outcome, str)
            else "outcome_not_recorded"
        )
    elif test_status == "failed":
        actual_outcome = "test_failed"
    else:
        actual_outcome = "unavailable"

    retry_count = properties.get("retry_count")
    if (
        is_duplicate
        or isinstance(retry_count, bool)
        or not isinstance(retry_count, int)
        or retry_count < 0
    ):
        retry_count = None

    error_category = properties.get("error_category")
    if is_duplicate:
        error_category = "duplicate_scenario_result"
    elif error_category not in SAFE_ERROR_CATEGORIES:
        error_category = collector.error_categories.get(scenario.node_id)

    passed = test_status == "passed" and actual_outcome == scenario.expected_outcome
    if test_status == "passed" and not passed and error_category is None:
        error_category = "outcome_mismatch"

    return {
        "scenario_id": scenario.scenario_id,
        "test_node_id": scenario.node_id,
        "expected_outcome": scenario.expected_outcome,
        "actual_outcome": actual_outcome,
        "test_status": test_status,
        "passed": passed,
        "elapsed_seconds": collector.elapsed_seconds.get(scenario.node_id),
        "execution_count": execution_count,
        "retry_count": retry_count,
        "error_category": error_category,
    }


def _scenario_results(
    scenarios: tuple[Scenario, ...],
    collector: EvaluationCollector,
) -> list[dict[str, Any]]:
    scenario_id_counts = Counter(scenario.scenario_id for scenario in scenarios)
    node_id_counts = Counter(scenario.node_id for scenario in scenarios)
    return [
        _scenario_result(
            scenario,
            collector,
            duplicate=(
                scenario_id_counts[scenario.scenario_id] > 1
                or node_id_counts[scenario.node_id] > 1
            ),
        )
        for scenario in scenarios
    ]


def _build_markdown(report: dict[str, Any]) -> str:
    totals = report["totals"]
    lines = [
        "# Sentinel Deterministic Evaluation",
        "",
        f"- Run timestamp (UTC): `{report['run_timestamp_utc']}`",
        f"- Runner status: {report['runner_status']}",
        f"- Pytest exit code: {report['pytest_exit_code']}",
        f"- Scenarios: {totals['scenario_count']}",
        f"- Passed: {totals['passed']}",
        f"- Failed: {totals['failed']}",
        f"- Unavailable: {totals['unavailable']}",
        (
            f"- Pass rate: {totals['pass_rate']:.3f} "
            f"({totals['passed']} / {totals['scenario_count']}; denominator includes skipped and uncollected scenarios)"
        ),
        "",
        "This is a deterministic fixture result, not a live-model benchmark.",
        "Elapsed time covers the full pytest test protocol and is measured with a monotonic clock.",
        "",
        "| Scenario | Expected | Actual | Test status | Pass | Executions | Duration (s) | Retries | Error category |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for scenario in report["scenarios"]:
        duration = scenario["elapsed_seconds"]
        duration_text = f"{duration:.3f}" if duration is not None else "Unavailable"
        retry_text = (
            str(scenario["retry_count"])
            if scenario["retry_count"] is not None
            else "Unavailable"
        )
        error_category = scenario["error_category"] or "None"
        lines.append(
            f"| {scenario['scenario_id']} | {scenario['expected_outcome']} | "
            f"{scenario['actual_outcome']} | {scenario['test_status']} | "
            f"{scenario['passed']} | {scenario['execution_count']} | "
            f"{duration_text} | {retry_text} | {error_category} |"
        )
    return "\n".join(lines) + "\n"


def _write_reports(
    output_dir: Path,
    run_id: str,
    report: dict[str, Any],
) -> tuple[Path, Path]:
    json_content = json.dumps(report, indent=2, sort_keys=True) + "\n"
    markdown_content = _build_markdown(report)
    suffix = 0

    while True:
        candidate_id = run_id if suffix == 0 else f"{run_id}-{suffix}"
        json_path = output_dir / f"sentinel-evaluation-{candidate_id}.json"
        markdown_path = output_dir / f"sentinel-evaluation-{candidate_id}.md"
        created_json = False
        try:
            with json_path.open("x", encoding="utf-8") as json_file:
                json_file.write(json_content)
            created_json = True
            with markdown_path.open("x", encoding="utf-8") as markdown_file:
                markdown_file.write(markdown_content)
            return json_path, markdown_path
        except FileExistsError:
            if created_json:
                json_path.unlink(missing_ok=True)
            suffix += 1


def _evaluation_exit_code(
    pytest_exit_code: int,
    scenario_results: list[dict[str, Any]],
) -> int:
    if pytest_exit_code != 0 or any(
        not result["passed"] for result in scenario_results
    ):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Sentinel's deterministic autonomous-repair evaluation scenarios."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and Markdown reports (default: data/evaluation-reports).",
    )
    arguments = parser.parse_args(argv)

    os.chdir(REPOSITORY_ROOT)
    sys.path.insert(0, str(REPOSITORY_ROOT))
    run_timestamp = datetime.now(UTC)
    run_id = run_timestamp.strftime("%Y%m%dT%H%M%S.%fZ")
    output_dir = arguments.output_dir
    if not output_dir.is_absolute():
        output_dir = REPOSITORY_ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    collector = EvaluationCollector()
    pytest_exit_code = int(
        pytest.main(
            ["-q", *(scenario.node_id for scenario in SCENARIOS)],
            plugins=[collector],
        )
    )
    scenario_results = _scenario_results(SCENARIOS, collector)
    passed_count = sum(result["passed"] for result in scenario_results)
    unavailable_count = sum(
        result["test_status"] in {"skipped", "not_collected"}
        for result in scenario_results
    )
    failed_count = len(SCENARIOS) - passed_count - unavailable_count
    evaluation_exit_code = _evaluation_exit_code(pytest_exit_code, scenario_results)
    report = {
        "schema_version": 1,
        "suite_id": "sentinel_deterministic_autonomous_repair",
        "run_timestamp_utc": run_timestamp.isoformat(),
        "live_model_evaluation": False,
        "pytest_exit_code": pytest_exit_code,
        "runner_status": "passed" if evaluation_exit_code == 0 else "failed",
        "totals": {
            "scenario_count": len(SCENARIOS),
            "passed": passed_count,
            "failed": failed_count,
            "unavailable": unavailable_count,
            "pass_rate": passed_count / len(SCENARIOS),
            "pass_rate_denominator": (
                "all configured scenarios, including skipped and not collected"
            ),
        },
        "scenarios": scenario_results,
    }

    json_path, markdown_path = _write_reports(output_dir, run_id, report)

    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    print(
        f"Scenarios: {len(SCENARIOS)}; passed: {passed_count}; "
        f"failed: {failed_count}; unavailable: {unavailable_count}"
    )

    return evaluation_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
