import json
from typing import Any

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

        if not isinstance(summary, str):
            raise TypeError("Summary must be a string.")

        if not isinstance(raw_steps, list):
            raise TypeError("Steps must be a list.")

        steps = tuple(
            _parse_step(step)
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
            "LLM response does not match " "the investigation plan schema."
        ) from exc


def _parse_step(
        step: dict[str, Any],
) -> PlanStep:
    """Parse a single investigation plan step."""
    arguments = step.get("arguments", {})

    if not isinstance(arguments, dict):
        raise TypeError(
        "Step arguments must be an object."
    )

    return PlanStep(
        step_number=step["step_number"],
        action=PlanStepType(step["action"]),
        description=step["description"],
        arguments=arguments,
)
