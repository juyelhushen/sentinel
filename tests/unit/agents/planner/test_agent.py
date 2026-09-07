import pytest

from sentinel.agents.planner.agent import PlannerAgent
from sentinel.agents.planner.parser import PlanParsingError
from sentinel.domain.models.incident import Incident
from sentinel.llm.base import LLMProvider
from sentinel.llm.models import LLMRequest, LLMResponse


class FakeLLMProvider(LLMProvider):
    """Deterministic LLM provider for PlannerAgent tests."""

    def __init__(self, response_content: str) -> None:
        self.response_content = response_content

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content=self.response_content,
            model="fake_model",
            request_id=request.request_id,
        )

    async def health_check(self) -> bool:
        return True

@pytest.mark.asyncio
async def test_planner_agent_creates_structured_plan() -> None:
    provider = FakeLLMProvider(
        response_content="""
        {
        "summary": "Investigate failing tests",
        "steps": [{
        "step_number": 1,
        "action": "run_tests",
        "description": "Run the failing test suite."
        }
        ]
         }
         """
    )

    agent = PlannerAgent(
        llm_provider=provider,
    )

    incident = Incident(
        title="Tests are failing",
        description="Tests started failing after a recent change.",
        repository="sentinel", )
    plan = await agent.plan(incident)

    assert plan.summary == "Investigate failing tests"
    assert len(plan.steps) == 1
    assert plan.steps[0].action.value == "run_tests"

@pytest.mark.asyncio
async def test_planner_agent_rejects_invalid_llm_response() -> None:
    provider = FakeLLMProvider(
        response_content="This is not valid JSON."
    )

    agent = PlannerAgent(
    llm_provider=provider,
    )

    incident = Incident(
    title="Tests are failing",
    description="Tests started failing after a recent change.",
    repository="sentinel",
    )

    with pytest.raises(PlanParsingError):
        await agent.plan(incident)