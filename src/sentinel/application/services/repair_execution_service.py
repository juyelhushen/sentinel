from sentinel.application.ports.tool_gateway import ToolGateway
from sentinel.domain.repair import RepairPlan
from sentinel.tools.models import ToolResult, ToolRequest


class RepairExecutionService:
    def __init__(self, tool_gateway: ToolGateway) -> None:
        self._tool_gateway = tool_gateway

    async def execute(self, repair_plan: RepairPlan) -> tuple[ToolResult, ...]:
        results: list[ToolResult] = []

        for step in repair_plan.steps:
            request = ToolRequest(
                tool_name=step.action.value,
                arguments={
                    "file_path": step.file_path,
                    "patch": step.patch,
                },
            )

            result = await self._tool_gateway.execute(request)
            results.append(result)

            if not result.succeeded:
                break

        return tuple(results)