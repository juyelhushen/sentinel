from sentinel.application.ports.repair_repository import RepairRepository
from sentinel.application.repair.repair_agent import RepairAgent
from sentinel.application.services.repair_execution_service import (
    RepairExecutionService,
)
from sentinel.domain.repair.attempt import RepairAttempt
from sentinel.workflows.graph_state import SentinelGraphState


def repair_plan_node(
    repair_agent: RepairAgent,
):
    async def node(state: SentinelGraphState) -> dict:
        incident = state.get("incident")
        if incident is None:
            raise ValueError("Cannot create repair plan without an incident.")

        investigation = state.get("investigation")

        if investigation is None:
            raise ValueError("Cannot create repair plan without investigation.")

        previous_attempts = state.get(
            "repair_attempts",
            (),
        )

        repair_plan = await repair_agent.create_plan(
            incident=incident,
            investigation=investigation,
            previous_attempts=previous_attempts,
        )

        return {
            "repair_plan": repair_plan,
        }

    return node


def repair_node(
    repair_execution_service: RepairExecutionService,
):
    async def node(state: SentinelGraphState) -> dict:
        repair_plan = state.get("repair_plan")

        if repair_plan is None:
            raise ValueError("Cannot execute repair without a repair plan.")

        results = await repair_execution_service.execute(
            repair_plan,
        )

        if not results:
            return {
                "error": "Repair was not executed.",
                "verification": None,
            }

        failed_result = next(
            (result for result in results if not result.succeeded),
            None,
        )

        if failed_result is not None:
            return {
                "error": failed_result.error or "Repair execution failed.",
                "verification": None,
            }

        return {
            "error": None,
            "verification": None,
        }

    return node


async def record_repair_attempt_node(
    state: SentinelGraphState,
    repair_repository: RepairRepository | None = None,
) -> dict:
    repair_plan = state.get("repair_plan")

    if repair_plan is None:
        raise ValueError("Cannot record repair attempt without repair plan.")

    attempts = state.get(
        "repair_attempts",
        (),
    )

    verification = state.get("verification")
    approval = state.get("approval")

    attempt = RepairAttempt(
        attempt_number=len(attempts) + 1,
        repair_plan=repair_plan,
        verification=verification,
        approval=approval,
        execution_error=state.get("error"),
    )

    execution = state.get("execution")
    if repair_repository is not None:
        if execution is None:
            raise ValueError("Cannot persist repair attempt without execution.")
        await repair_repository.save_attempt(execution.id, attempt)

    return {
        "repair_attempts": (*attempts, attempt),
    }
