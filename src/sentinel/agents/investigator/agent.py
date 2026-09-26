from typing import Protocol

from sentinel.agents.investigator.mapper import map_plan_step_to_tool_request
from sentinel.agents.investigator.models import (
    InvestigationResult,
    StepInvestigationResult,
)
from sentinel.agents.planner.models import InvestigationPlan, PlanStepType
from sentinel.application.ports.tool_gateway import ToolGateway
from sentinel.tools.models import ToolRequest, ToolResult


class ToolExecutorProtocol(Protocol):
    async def execute(self, request: ToolRequest) -> ToolResult:
        """Execute a tool request."""


class InvestigatorAgent:
    """Executes investigation plans using controlled tools."""

    def __init__(
        self,
        tool_gateway: ToolGateway,
    ) -> None:
        self.tool_gateway = tool_gateway


    async def investigate(
        self,
        plan: InvestigationPlan,
    ) -> InvestigationResult:
        """Execute an investigation plan"""

        steps_results: list[StepInvestigationResult] = []

        for step in plan.steps:
            request = map_plan_step_to_tool_request(step)

            tool_result = await self.tool_gateway.execute(
                request,
            )

            steps_results.append(
                StepInvestigationResult(
                    step_number=step.step_number,
                    action=step.action,
                    success=tool_result.succeeded,
                    findings=self._build_findings(
                        step.action,
                        tool_result=tool_result,
                    ),
                )
            )

        return InvestigationResult(
            summary=self._build_summary(step_results=steps_results),
            step_results=tuple(steps_results),
        )

    @staticmethod
    def _build_findings(
        step_action: PlanStepType,
        tool_result: ToolResult,
    ) -> str:
        """Convert a tool result into investigation findings."""

        if tool_result.succeeded and step_action == PlanStepType.RUN_TESTS:
            findings = "Tests passed"
        elif tool_result.succeeded:
            output = tool_result.output

            if not isinstance(output, str):
                findings = str(output)
            else:
                text = output.strip()

                if not text:
                    findings = "Tool execution completed"
                elif text.endswith((".", "!", "?")):
                    findings = text
                else:
                    findings = f"{text}"
        else:
            findings = tool_result.error or "Tool execution failed"

        # Normalize: ensure non-empty findings end with exactly one period
        if findings:
            findings = findings.rstrip(".") + "."
        else:
            findings = "No findings."

        return findings

    @staticmethod
    def _build_summary(step_results: list[StepInvestigationResult]) -> str:
        """Build a summary of the investigation."""
        if not step_results:
            return "No investigation steps were executed."

        successful_steps = sum(result.success for result in step_results)

        return (
            f"Investigation completed: "
            f"{successful_steps}/{len(step_results)} "
            f"steps succeeded."
        )
