from sentinel.agents.investigator.models import InvestigationResult
from sentinel.application.repair.repair_parser import parse_repair_plan
from sentinel.application.repair.repair_prompt import build_repair_prompt
from sentinel.domain.models.incident import Incident
from sentinel.domain.repair import RepairPlan
from sentinel.domain.repair.attempt import RepairAttempt
from sentinel.llm.base import LLMProvider
from sentinel.llm.models import LLMRequest


class RepairAgent:
    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm_provider = llm_provider

    async def create_plan(
        self,
        incident: Incident,
        investigation: InvestigationResult,
        previous_attempts: tuple[RepairAttempt, ...] = ()
    ) -> RepairPlan:
        prompt = build_repair_prompt(
            incident=incident,
            investigation=investigation,
            previous_attempts=previous_attempts,
        )

        request = LLMRequest(
            messages=prompt.to_message(),
            temperature=0.0,
        )

        response = await self._llm_provider.generate(request)

        return parse_repair_plan(response.content)