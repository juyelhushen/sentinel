from urllib import response

from sentinel.agents.planner.models import InvestigationPlan
from sentinel.agents.planner.parser import parse_investigation_plan
from sentinel.agents.planner.prompt import build_planner_prompt
from sentinel.domain.models.incident import Incident
from sentinel.llm.base import LLMProvider
from sentinel.llm.models import LLMRequest


class PlannerAgent:
    """Creates investigation plans for incidents"""

    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    async def plan(
        self,
        incident: Incident,
    ) -> InvestigationPlan:
        """Create an investigation plan for an incident."""

        prompt = build_planner_prompt(incident)
 
        request = LLMRequest(
            messages=prompt.to_message(),
            temperature=0.0
        )

        response = await self.llm_provider.generate(request)

        return parse_investigation_plan( response.content )
