from sentinel.domain.models.incident import Incident
from sentinel.llm.prompts.base import Prompt


def build_planner_prompt(incident: Incident) -> Prompt:
    """Build a prompt used by the Planner Agents."""

    return Prompt(
        system=(
            "You are Sentinel's planning agent for software engineering incidents. "
            "Your responsibility is to create a concise investigation plan. "
            "Do not attempt to fix the problem. "
            "Do not execute tools. "
            "Only determine what investigation steps should happen."
        ),
        user=(
            f"Incident title: {incident.title}\n"
            f"Incident description: {incident.description}\n"
            f"Repository: {incident.repository}\n\n"
            "Create an investigation plan using only the following actions:\n"
            "- inspect_file\n"
            "- search_code\n"
            "- run_tests\n"
            "- analyze_logs\n\n"
            "Return ONLY valid JSON using exactly this structure:\n"
            "{\n"
            ' "summary": "short description of the investigation",\n'
            ' "steps": [\n'
            " {\n"
            ' "step_number": 1,\n'
            ' "action": "run_tests",\n'
            ' "description": "description of what should be done"\n'
            " }\n"
            " ]\n"
            "}\n\n"
            "Do not include markdown code fences. "
            "Do not include any explanation outside the JSON."
        ),
    )
