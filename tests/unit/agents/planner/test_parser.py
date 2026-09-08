import pytest

from sentinel.agents.planner.models import PlanStepType
from sentinel.agents.planner.parser import (
    PlanParsingError,
    parse_investigation_plan,
)


def test_parse_investigation_plan() -> None:
    content = """
     {
        "summary": "Investigate failing tests",
        "steps": [
            {
                "step_number": 1,
                "action": "run_tests",
                "description": "Run the failing tests."
            },
            {
                "step_number": 2,
                "action": "inspect_file",
                "description": "Inspect the affected source files."
            }
        ]
    }
    """

    plan = parse_investigation_plan(content)

    assert plan.summary == "Investigate failing tests"
    assert len(plan.steps) == 2
    assert plan.steps[0].action == PlanStepType.RUN_TESTS
    

def test_parse_investigation_plan_rejects_invalid_json() -> None:
    with pytest.raises(PlanParsingError):
        parse_investigation_plan(
            "This is not JSON."
        )

def test_parse_investigation_plan_rejects_invalid_action() -> None:
    content = """
    {
        "summary": "Investigate issue",
        "steps": [
            {
                "step_number": 1,
                "action": "delete_everything",
                "description": "Bad action."
            }
        ]
    }
    """

    with pytest.raises(PlanParsingError):
        parse_investigation_plan(content)


def test_parse_investigation_plan_with_arguments() -> None:
    content = """
    {
        "summary": "Investigate token validation.",
        "steps": [
            {
                "step_number": 1,
                "action": "search_code",
                "description": "Find token validation code.",
                "arguments": {
                    "query": "validate_token"
                }
            }
        ]
    }
    """

    plan = parse_investigation_plan(content)

    assert plan.summary == "Investigate token validation."
    assert len(plan.steps) == 1
    assert plan.steps[0].action == PlanStepType.SEARCH_CODE
    assert plan.steps[0].arguments == {
        "query": "validate_token",
    }


def test_parse_investigation_plan_defaults_missing_arguments() -> None:
    content = """
    {
        "summary": "Investigate token validation.",
        "steps": [
            {
                "step_number": 1,
                "action": "search_code",
                "description": "Find token validation code."
            }
        ]
    }
    """

    plan = parse_investigation_plan(content)

    assert plan.steps[0].arguments == {}


def test_parse_investigation_plan_rejects_invalid_arguments() -> None:
    content = """
    {
        "summary": "Investigate token validation.",
        "steps": [
            {
                "step_number": 1,
                "action": "search_code",
                "description": "Find token validation code.",
                "arguments": "validate_token"
            }
        ]
    }
    """

    with pytest.raises(PlanParsingError):
        parse_investigation_plan(content)
