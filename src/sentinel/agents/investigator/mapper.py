from sentinel.agents.planner.models import PlanStep
from sentinel.tools.models import ToolRequest

_ACTION_TO_TOOL: dict[str, str] = {
    "inspect_file": "read_file",
    "search_code": "search_code",
    "run_tests": "run_tests",
    "analyze_logs": "analyze_logs",
}

def map_plan_step_to_tool_request(
    step: PlanStep,
) -> ToolRequest:
    """Convert a plan step into a controlled tool request."""

    try:
        tool_name = _ACTION_TO_TOOL[step.action.value]
    except KeyError as exc:
        raise ValueError(
            f"No tool mapping exists for action: {step.action.value}"
        ) from exc

    return ToolRequest(
        tool_name=tool_name,
        arguments={
            "description": step.description,
        },
    )
