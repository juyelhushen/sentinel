from sentinel.domain.models.incident import Incident
from sentinel.llm.prompts.base import Prompt


def build_planner_prompt(incident: Incident) -> Prompt:
    """Build a prompt used by the Planner Agent."""

    return Prompt(
        system=(
            "You are Sentinel's planning agent for software engineering "
            "incidents. "
            "Your responsibility is to create a concise investigation plan. "
            "Do not attempt to fix the problem. "
            "Do not execute tools. "
            "Only determine what investigation steps should happen. "
            "\n\n"
            "You may only use the following actions and argument schemas:\n\n"
            "1. inspect_file\n"
            'Arguments: {"path": "relative/path/to/file"}\n\n'
            "2. search_code\n"
            'Arguments: {"query": "text to search for"}\n\n'
            "3. run_tests\n"
            'Arguments: {"test_path": "relative/path/or/test/directory"}\n\n'
            "4. analyze_logs\n"
            'Arguments: {"path": "relative/path/to/log/file"}\n\n'
            "Rules:\n"
            "- Use only the supported actions.\n"
            "- Every step must contain step_number, action, description, "
            "and arguments.\n"
            "- arguments must always be a JSON object.\n"
            "- Use repository-relative paths only.\n"
            "- Never use absolute paths.\n"
            "- Create only the minimum steps needed to investigate the "
            "incident."
        ),
        user=(
            f"Incident title: {incident.title}\n"
            f"Incident description: {incident.description}\n"
            f"Repository: {incident.repository}\n\n"
            "Create an investigation plan.\n\n"
            "Return ONLY valid JSON using exactly this structure:\n"
            "{\n"
            '  "summary": "short description of the investigation",\n'
            '  "steps": [\n'
            "    {\n"
            '      "step_number": 1,\n'
            '      "action": "search_code",\n'
            '      "description": "description of what should be done",\n'
            '      "arguments": {\n'
            '        "query": "example_function"\n'
            "      }\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Do not include markdown code fences. "
            "Do not include any explanation outside the JSON."
        ),
    )
