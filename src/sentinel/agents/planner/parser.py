import json

from sentinel.agents.planner.models import InvestigationPlan, PlanStep, PlanStepType


class PlanParsingError(ValueError):
    """Raised when an investigation plan cannot be parsed."""

def parse_investigation_plan(
    content: str,
) -> InvestigationPlan:
    """Parse LLM JSON output into an InvestigationPlan."""

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise PlanParsingError("LLM response is not valid JSON.") from exc

    try:
        summary = data["summary"]
        raw_steps = data["steps"]

        steps = tuple(
            PlanStep(
                step_number=step["step_number"],
                action=PlanStepType(step["action"]),
                description=step["description"],
            )
            for step in raw_steps
        )

        return InvestigationPlan(
            summary=summary,
            steps=steps,
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise PlanParsingError(
            "LLM response does not match the investigation plan schema."
        ) from exc
