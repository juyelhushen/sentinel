import pytest

from sentinel.agents.investigator.mapper import map_plan_step_to_tool_request
from sentinel.agents.planner.models import PlanStepType, PlanStep


@pytest.mark.parametrize(
    ("action", "arguments", "expected_tool"),
    [
        (PlanStepType.INSPECT_FILE,{"path": "src/service.py"}, "read_file",),
        (PlanStepType.SEARCH_CODE,{"query": "validate_token"}, "search_code",),
        (PlanStepType.RUN_TESTS,{"test_path": "tests"}, "run_tests",),
        (PlanStepType.ANALYZE_LOGS,{"path": "logs/application.log"}, "analyze_logs",),
    ],
                         )
def test_map_plan_step_to_tool_request(
        action: PlanStepType,
        arguments: dict,
        expected_tool: str,
) -> None:
    step = PlanStep(
        step_number=1,
        action=action,
        description="Perform investigation.",
        arguments=arguments,
    )

    request = map_plan_step_to_tool_request(step)

    assert request.tool_name == expected_tool
    assert request.arguments == arguments


def test_map_plan_step_to_tool_request_creates_request_id() -> None:
    step = PlanStep(
        step_number=1,
        action=PlanStepType.RUN_TESTS,
        description="Run the test suite.",
        arguments={
            "test_path": "tests",
        }
    )
    
    request = map_plan_step_to_tool_request(step)
    assert request.request_id is not None

