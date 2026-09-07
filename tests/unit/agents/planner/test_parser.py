import pytest

from sentinel.agents.planner.models import PlanStepType
from sentinel.agents.planner.parser import parse_investigation_plan, PlanParsingError


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
