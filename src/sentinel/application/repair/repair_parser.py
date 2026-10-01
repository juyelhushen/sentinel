import json

from sentinel.domain.repair import RepairPlan, RepairStep, RepairStepType


class RepairParsingError(ValueError):
    """Raised when an LLM repair response is invalid."""


def parse_repair_plan(content: str) -> RepairPlan:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RepairParsingError(
            "Repair response is not valid JSON."
        ) from exc

    if not isinstance(data, dict):
        raise RepairParsingError(
            "Repair response must be a JSON object."
        )

    summary = data.get("summary")
    steps = data.get("steps")

    if not isinstance(summary, str):
        raise RepairParsingError(
            "Repair plan summary must be a string."
        )

    if not isinstance(steps, list):
        raise RepairParsingError(
            "Repair plan steps must be a list."
        )

    parsed_steps: list[RepairStep] = []

    for index, raw_step in enumerate(steps, start=1):
        if not isinstance(raw_step, dict):
            raise RepairParsingError(
                f"Repair step {index} must be an object."
            )

        step_number = raw_step.get("step_number")
        action = raw_step.get("action")
        file_path = raw_step.get("file_path")
        description = raw_step.get("description")
        patch = raw_step.get("patch")

        if not isinstance(step_number, int):
            raise RepairParsingError(
                f"Repair step {index} has invalid step_number."
            )

        if action != RepairStepType.APPLY_PATCH.value:
            raise RepairParsingError(
                f"Unsupported repair action: {action}"
            )

        if not isinstance(file_path, str):
            raise RepairParsingError(
                f"Repair step {index} has invalid file_path."
            )

        if not isinstance(description, str):
            raise RepairParsingError(
                f"Repair step {index} has invalid description."
            )

        if not isinstance(patch, str):
            raise RepairParsingError(
                f"Repair step {index} has invalid patch."
            )

        parsed_steps.append(
            RepairStep(
                step_number=step_number,
                action=RepairStepType.APPLY_PATCH,
                file_path=file_path,
                description=description,
                patch=patch,
            )
        )

    return RepairPlan(
        summary=summary,
        steps=tuple(parsed_steps),
    )