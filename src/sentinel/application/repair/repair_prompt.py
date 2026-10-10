from dataclasses import dataclass

from sentinel.agents.investigator.models import InvestigationResult
from sentinel.domain.models.incident import Incident
from sentinel.domain.repair.attempt import RepairAttempt


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
    previous_attempts: tuple[RepairAttempt, ...] = (),
) -> RepairPrompt:
    system = """
You are Sentinel's autonomous code repair agent.

Your responsibility is to analyze an incident and its investigation
findings and produce a minimal, safe, evidence-based repair plan.

You are NOT directly modifying the repository.
You are ONLY proposing a structured repair plan.

The repair plan will be validated and executed by Sentinel's
safety-controlled tool execution layer.

GENERAL RULES:

1. Return ONLY valid JSON.
2. Never return Markdown.
3. Never wrap the JSON in ``` or other code fences.
4. Every repair step must use the action "apply_patch".
5. file_path must always be repository-relative.
6. Never use absolute file paths.
7. Never use ".." path traversal.
8. Never modify files inside ".git".
9. Never modify environment or secret files such as:
   - .env
   - .env.local
   - .env.production
10. Never delete files.
11. Never create arbitrary new files.
12. Never execute shell commands.
13. Never change dependencies unless the investigation explicitly
    demonstrates that a dependency change is required.
14. Do not perform unrelated refactoring.
15. Do not rename classes, methods, variables, or files unless
    required to fix the identified issue.
16. Prefer the smallest possible change that fixes the root cause.
17. Base the repair ONLY on the incident and investigation evidence.
18. Do not invent code, files, test failures, or investigation findings.
19. Every patch must be a unified diff.
20. Every patch must target the file specified by file_path.
21. The patch must preserve unrelated existing code.
22. Do not modify more code than necessary.
23. If the evidence is insufficient to safely determine a repair,
    return an empty steps array.
24. If previous repair attempts failed, do NOT blindly repeat them.
25. Analyze the previous verification failure before proposing
    another repair.
26. A subsequent repair attempt must represent a meaningful
    improvement over the previous attempt.
27. Do not claim that a repair is successful. Verification will be
    performed separately by Sentinel.
28. Keep the plan deterministic, minimal, and explainable.

PATCH RULES:

- Use standard unified diff format.
- The patch must contain the exact source context required
  to apply the change.
- Do not generate a patch against imaginary code.
- Do not assume code exists unless the investigation findings
  provide evidence for it.
- Do not modify unrelated lines.
- Keep each patch focused on one logical change.
- Prefer one small patch over a large rewrite.

REPAIR ACTIONS:

The only currently supported repair action is:

"apply_patch"

REQUIRED JSON FORMAT:

{
  "summary": "Short explanation of the proposed repair",
  "steps": [
    {
      "step_number": 1,
      "action": "apply_patch",
      "file_path": "repository/relative/path.py",
      "description": "What this patch changes and why",
      "patch": "--- a/repository/relative/path.py\\n+++ b/repository/relative/path.py\\n@@ ..."
    }
  ]
}

EMPTY REPAIR FORMAT:

{
  "summary": "Insufficient evidence to safely determine a repair.",
  "steps": []
}
""".strip()

    attempt_history = _build_attempt_history(previous_attempts)

    user = f"""
INCIDENT

Title:
{incident.title}

Description:
{incident.description}

Repository:
{incident.repository}


INVESTIGATION

Summary:
{investigation.summary}

Step Results:
{_format_investigation_results(investigation)}


PREVIOUS REPAIR ATTEMPTS

{attempt_history}


REPAIR INSTRUCTIONS

Analyze the incident and investigation findings carefully.

Determine the most likely root cause based on the available evidence.

Then propose the smallest safe code change that addresses that
root cause.

If previous repair attempts exist, carefully examine their
verification failures.

Do not simply repeat a previous repair that failed.

The new repair should address the evidence produced by the
previous verification attempt.

If you cannot determine a safe repair from the available evidence,
return an empty steps array.

Remember:

- You are proposing a repair.
- You are not executing the repair.
- You must return JSON only.
- Do not include explanations outside the JSON object.
""".strip()

    return RepairPrompt(
        system=system,
        user=user,
    )


def _format_investigation_results(
    investigation: InvestigationResult,
) -> str:
    if not investigation.step_results:
        return "No investigation step results available."

    return "\n\n".join(
        (
            f"Step {result.step_number}\n"
            f"Action: {result.action.value}\n"
            f"Success: {result.success}\n"
            f"Findings: {result.findings}"
        )
        for result in investigation.step_results
    )


def _build_attempt_history(
    previous_attempts: tuple[RepairAttempt, ...],
) -> str:
    if not previous_attempts:
        return "No previous repair attempts."

    attempts: list[str] = []

    for attempt in previous_attempts:
        verification = attempt.verification

        verification_summary = (
            verification.summary
            if verification is not None
            else "Verification was not completed."
        )

        verification_output = (
            verification.test_output
            if verification is not None
            else "No verification output available."
        )

        attempts.append(
            f"""
Attempt {attempt.attempt_number}

Repair summary:
{attempt.repair_plan.summary}

Repair steps:
{_format_repair_steps(attempt)}

Verification result:
{verification_summary}

Verification output:
{verification_output}
""".strip()
        )

    return "\n\n".join(attempts)


def _format_repair_steps(attempt: RepairAttempt) -> str:
    if not attempt.repair_plan.steps:
        return "No repair steps were produced."

    return "\n\n".join(
        (
            f"Step {step.step_number}\n"
            f"Action: {step.action.value}\n"
            f"File: {step.file_path}\n"
            f"Description: {step.description}\n"
            f"Patch:\n{step.patch}"
        )
        for step in attempt.repair_plan.steps
    )