import pytest

from sentinel.agents.investigator.mapper import map_plan_step_to_tool_request
from sentinel.agents.planner.models import PlanStepType, PlanStep


@pytest.mark.parametrize(
    ("action", "expected_tool"),
    [
        (PlanStepType.INSPECT_FILE, "read_file",),
        (PlanStepType.SEARCH_CODE,"search_code",),
        (PlanStepType.RUN_TESTS,"run_tests",),
        (PlanStepType.ANALYZE_LOGS,"analyze_logs",),
    ],
                         )
def test_map_plan_step_to_tool_request(
        action: PlanStepType,
        expected_tool: str,
) -> None:
    step = PlanStep(
        step_number=1,
        action=action,
        description="Perform investigation.",
    )

    request = map_plan_step_to_tool_request(step)

    assert request.tool_name == expected_tool
    assert request.arguments == {
    "description": "Perform investigation."
    }


def test_map_plan_step_to_tool_request_creates_request_id() -> None:
    step = PlanStep(
        step_number=1,
        action=PlanStepType.RUN_TESTS,
        description="Run the test suite.",
    )
    
    request = map_plan_step_to_tool_request(step)
    assert request.request_id is not None

