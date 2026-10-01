import pytest

from sentinel.application.repair.repair_parser import (
    parse_repair_plan,
    RepairParsingError,
)
from sentinel.domain.repair import RepairStepType


def test_parses_valid_repair_plan() -> None:
    content = """
    {
      "summary": "Fix null handling",
      "steps": [
        {
          "step_number": 1,
          "action": "apply_patch",
          "file_path": "src/service.py",
          "description": "Add null check",
          "patch": "--- a/src/service.py\\n+++ b/src/service.py"
        }
      ]
    }
    """

    plan = parse_repair_plan(content)

    assert plan.summary == "Fix null handling"
    assert len(plan.steps) == 1
    assert plan.steps[0].action == RepairStepType.APPLY_PATCH
    assert plan.steps[0].file_path == "src/service.py"


def test_rejects_invalid_json() -> None:
    with pytest.raises(
        RepairParsingError,
        match="not valid JSON",
    ):
        parse_repair_plan("not json")


def test_rejects_non_object_response() -> None:
    with pytest.raises(
        RepairParsingError,
        match="must be a JSON object",
    ):
        parse_repair_plan("[]")


def test_rejects_missing_steps() -> None:
    content = """
    {
      "summary": "Fix issue"
    }
    """

    with pytest.raises(
        RepairParsingError,
        match="steps must be a list",
    ):
        parse_repair_plan(content)


def test_rejects_unsupported_action() -> None:
    content = """
    {
      "summary": "Fix issue",
      "steps": [
        {
          "step_number": 1,
          "action": "delete_file",
          "file_path": "src/service.py",
          "description": "Delete file",
          "patch": ""
        }
      ]
    }
    """

    with pytest.raises(
        RepairParsingError,
        match="Unsupported repair action",
    ):
        parse_repair_plan(content)


def test_allows_empty_repair_plan() -> None:
    content = """
    {
      "summary": "Insufficient evidence for safe repair",
      "steps": []
    }
    """

    plan = parse_repair_plan(content)

    assert plan.steps == ()