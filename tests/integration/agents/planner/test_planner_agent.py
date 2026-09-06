import pytest

from sentinel.agents.planner.agent import PlannerAgent
from sentinel.config.settings import get_settings
from sentinel.domain.models.incident import Incident
from sentinel.llm.ollama import OllamaProvider

@pytest.mark.asyncio
@pytest.mark.integration
async def test_planner_agent_creates_real_investigation_plan() -> None:
    settings = get_settings()

    provider = OllamaProvider(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )

    agent = PlannerAgent(
        llm_provider=provider,
    )

    incident = Incident(
        title="Authentication tests are failing",
        description=(
            "Several authentication tests started failing "
            "after a recent change to token validation."
        ),
        repository="sentinel",
    )

    plan = await agent.plan(incident)

    print(f"plan.summary: {plan.summary}")
    assert plan.summary
    assert len(plan.steps) > 0

    for step in plan.steps:
        assert step.step_number > 0
        assert step.description