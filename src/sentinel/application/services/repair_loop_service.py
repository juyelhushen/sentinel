from sentinel.agents.investigator.models import InvestigationResult
from sentinel.agents.verification.verification_agent import VerificationAgent
from sentinel.application.repair.repair_agent import RepairAgent
from sentinel.application.services.repair_execution_service import RepairExecutionService
from sentinel.domain.models.incident import Incident
from sentinel.domain.repair.attempt import RepairAttempt
from sentinel.domain.repair.retry import RepairRetryPolicy


class RepairLoopService:
    def __init__(
        self,
        repair_agent: RepairAgent,
        repair_execution_service: RepairExecutionService,
        verification_agent: VerificationAgent,
        retry_policy: RepairRetryPolicy,
    ) -> None:
        self._repair_agent = repair_agent
        self._repair_execution_service = repair_execution_service
        self._verification_agent = verification_agent
        self._retry_policy = retry_policy

    async def repair_and_verify(
        self,
        incident: Incident,
        investigation: InvestigationResult,
        verification_path: str,
    ) -> tuple[RepairAttempt, ...]:
        attempts: list[RepairAttempt] = []

        for attempt_number in range(
            1,
            self._retry_policy.max_attempts + 1,
        ):
            plan = await self._repair_agent.create_plan(
                incident=incident,
                investigation=investigation,
                previous_attempts=tuple(attempts),
            )

            results = await self._repair_execution_service.execute(plan)

            if not results:
                attempts.append(
                    RepairAttempt(
                        attempt_number=attempt_number,
                        repair_plan=plan,
                    )
                )
                break

            verification = await self._verification_agent.verify(
                test_path=verification_path,
            )

            attempt = RepairAttempt(
                attempt_number=attempt_number,
                repair_plan=plan,
                verification=verification,
            )

            attempts.append(attempt)

            if verification.passed:
                break

            if not self._retry_policy.can_retry(attempt_number):
                break

        return tuple(attempts)