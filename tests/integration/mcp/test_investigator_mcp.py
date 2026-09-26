import pytest

from sentinel.agents.investigator.agent import InvestigatorAgent
from sentinel.agents.planner.models import InvestigationPlan, PlanStep, PlanStepType
from sentinel.infrastructure.mcp.client import SentinelMCPClient
from sentinel.infrastructure.mcp.tool_gateway import MCPToolGateway


@pytest.mark.asyncio
async def test_investigator_executes_plan_through_mcp():
    client = SentinelMCPClient()

    try:
        await client.connect(
            command="uv",
            args=[
                "run",
                "python",
                "-m",
                "sentinel.infrastructure.mcp.stdio_server",
            ],
        )

        gateway = MCPToolGateway(client)

        investigator = InvestigatorAgent(
            tool_gateway=gateway,
        )

        plan = InvestigationPlan(
            summary="Inspect the MCP fixture.",
            steps=(
                PlanStep(
                    step_number=1,
                    action=PlanStepType.INSPECT_FILE,
                    description="Read the MCP fixture.",
                    arguments={
                        "path": "tests/fixtures/mcp/example.txt",
                    },
                ),
            ),
        )

        # Use the same Incident construction used by your
        # existing InvestigatorAgent tests.

        result = await investigator.investigate(plan)

        assert result.step_results
        assert result.step_results[0].success is True
        assert "Hello from Sentinel MCP!" in result.step_results[0].findings

    finally:
        await client.close()