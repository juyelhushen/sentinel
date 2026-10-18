import pytest

from scripts.run_evaluation import (
    SCENARIOS,
    EvaluationCollector,
    _evaluation_exit_code,
    _scenario_result,
    _scenario_results,
    _write_reports,
)


def test_evaluation_runner_passes_only_matching_recorded_outcomes() -> None:
    scenario = SCENARIOS[0]
    collector = EvaluationCollector()
    collector.phase_statuses[scenario.node_id] = {
        "setup": "passed",
        "call": "passed",
        "teardown": "passed",
    }
    collector.protocol_counts[scenario.node_id] = 1
    collector.properties[scenario.node_id] = {
        "evaluation_outcome": scenario.expected_outcome,
        "retry_count": 0,
    }
    collector.elapsed_seconds[scenario.node_id] = 0.25

    result = _scenario_result(scenario, collector)

    assert result["passed"] is True
    assert result["actual_outcome"] == scenario.expected_outcome
    assert result["retry_count"] == 0
    assert result["elapsed_seconds"] == 0.25
    assert _evaluation_exit_code(0, [result]) == 0


def test_evaluation_runner_marks_unavailable_without_zero_measurements() -> None:
    scenario = SCENARIOS[0]
    collector = EvaluationCollector()
    collector.phase_statuses[scenario.node_id] = {"setup": "skipped"}

    result = _scenario_result(scenario, collector)

    assert result["test_status"] == "skipped"
    assert result["actual_outcome"] == "unavailable"
    assert result["passed"] is False
    assert result["elapsed_seconds"] is None
    assert result["retry_count"] is None
    assert _evaluation_exit_code(0, [result]) != 0


def test_evaluation_runner_marks_missing_scenario_unavailable() -> None:
    result = _scenario_result(SCENARIOS[0], EvaluationCollector())

    assert result["test_status"] == "not_collected"
    assert result["actual_outcome"] == "unavailable"
    assert result["passed"] is False
    assert result["elapsed_seconds"] is None
    assert result["retry_count"] is None
    assert _evaluation_exit_code(0, [result]) != 0


def test_evaluation_runner_fails_duplicate_scenario_results() -> None:
    scenario = SCENARIOS[0]
    collector = EvaluationCollector()
    collector.phase_statuses[scenario.node_id] = {
        "setup": "passed",
        "call": "passed",
        "teardown": "passed",
    }
    collector.protocol_counts[scenario.node_id] = 2
    collector.properties[scenario.node_id] = {
        "evaluation_outcome": scenario.expected_outcome,
        "retry_count": 0,
    }

    result = _scenario_result(scenario, collector)

    assert result["test_status"] == "duplicate"
    assert result["actual_outcome"] == "duplicate_result"
    assert result["passed"] is False
    assert result["retry_count"] is None
    assert result["error_category"] == "duplicate_scenario_result"
    assert _evaluation_exit_code(0, [result]) != 0


def test_evaluation_runner_rejects_duplicate_registry_entries() -> None:
    scenario = SCENARIOS[0]
    results = _scenario_results((scenario, scenario), EvaluationCollector())

    assert len(SCENARIOS) == 6
    assert len({item.scenario_id for item in SCENARIOS}) == 6
    assert len({item.node_id for item in SCENARIOS}) == 6
    assert len(results) == 2
    assert all(result["test_status"] == "duplicate" for result in results)
    assert all(result["passed"] is False for result in results)
    assert _evaluation_exit_code(0, results) != 0


def test_evaluation_runner_fails_exit_for_pytest_failure_or_outcome_mismatch() -> None:
    assert _evaluation_exit_code(2, [{"passed": True}]) != 0
    assert _evaluation_exit_code(0, [{"passed": False}]) != 0


def test_evaluation_runner_marks_outcome_mismatch_as_failure() -> None:
    scenario = SCENARIOS[0]
    collector = EvaluationCollector()
    collector.phase_statuses[scenario.node_id] = {"call": "passed"}
    collector.protocol_counts[scenario.node_id] = 1
    collector.properties[scenario.node_id] = {
        "evaluation_outcome": "unexpected_outcome",
        "retry_count": 0,
    }

    result = _scenario_result(scenario, collector)

    assert result["test_status"] == "passed"
    assert result["passed"] is False
    assert result["error_category"] == "outcome_mismatch"
    assert _evaluation_exit_code(0, [result]) != 0


def test_evaluation_runner_marks_failed_test_as_failure() -> None:
    scenario = SCENARIOS[0]
    collector = EvaluationCollector()
    collector.phase_statuses[scenario.node_id] = {
        "setup": "passed",
        "call": "failed",
    }
    collector.protocol_counts[scenario.node_id] = 1
    collector.error_categories[scenario.node_id] = "test_call_failure"

    result = _scenario_result(scenario, collector)

    assert result["test_status"] == "failed"
    assert result["actual_outcome"] == "test_failed"
    assert result["passed"] is False
    assert result["error_category"] == "test_call_failure"
    assert _evaluation_exit_code(0, [result]) != 0


@pytest.mark.parametrize("existing_extension", ["json", "md"])
def test_evaluation_runner_does_not_overwrite_prior_reports(
    tmp_path,
    existing_extension: str,
) -> None:
    existing_file = tmp_path / f"sentinel-evaluation-fixed.{existing_extension}"
    existing_file.write_text("preserve this report", encoding="utf-8")
    report = {
        "run_timestamp_utc": "2026-10-19T00:00:00+00:00",
        "runner_status": "passed",
        "pytest_exit_code": 0,
        "totals": {
            "scenario_count": 1,
            "passed": 1,
            "failed": 0,
            "unavailable": 0,
            "pass_rate": 1.0,
        },
        "scenarios": [
            {
                "scenario_id": "sample",
                "expected_outcome": "success",
                "actual_outcome": "success",
                "test_status": "passed",
                "passed": True,
                "execution_count": 1,
                "elapsed_seconds": 0.1,
                "retry_count": 0,
                "error_category": None,
            }
        ],
    }

    json_path, markdown_path = _write_reports(tmp_path, "fixed", report)

    assert existing_file.read_text(encoding="utf-8") == "preserve this report"
    assert json_path.name == "sentinel-evaluation-fixed-1.json"
    assert markdown_path.name == "sentinel-evaluation-fixed-1.md"
    assert json_path.exists()
    assert markdown_path.exists()
