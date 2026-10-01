from dataclasses import dataclass

from sentinel.agents.investigator.models import InvestigationResult
from sentinel.domain.models.incident import Incident


@dataclass(frozen=True)
class RepairPrompt:
    system: str
    user: str

    def to_message(self) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": self.system,
            },
            {
                "role": "user",
                "content": self.user,
            },
        ]


def build_repair_prompt(
    incident: Incident,
    investigation: InvestigationResult,
) -> RepairPrompt:
    system = """
You are Sentinel's autonomous code repair agent.

Your responsibility is to create a minimal, safe repair plan
based only on the provided incident and investigation findings.

Rules:

1. Return ONLY valid JSON.
2. Do not use Markdown code fences.
3. Every repair step must use action "apply_patch".
4. file_path must be repository-relative.
5. Never use absolute paths.
6. Never modify .git or environment files.
7. Prefer the smallest possible code change.
8. Do not introduce unrelated refactoring.
9. Do not invent files or findings.
10. The patch must be a unified diff.
11. Each step must contain a complete patch.
12. If the evidence is insufficient to safely repair the issue,
    return an empty steps array.
13. Keep the repair plan deterministic and minimal.

Required JSON structure:

{
  "summary": "short explanation",
  "steps": [
    {
      "step_number": 1,
      "action": "apply_patch",
      "file_path": "repository/relative/path.py",
      "description": "what the patch changes",
      "patch": "unified diff"
    }
  ]
}
""".strip()

    user = f"""
Incident:

Title:
{incident.title}

Description:
{incident.description}

Repository:
{incident.repository}

Investigation summary:
{investigation.summary}

Investigation step results:
{investigation.step_results}
""".strip()

    return RepairPrompt(
        system=system,
        user=user,
    )