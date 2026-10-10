from sentinel.agents.verification.verification_agent import VerificationAgent
from sentinel.domain.enums.incident_status import IncidentStatus
from sentinel.domain.repair.retry import RepairRetryPolicy
from sentinel.workflows.graph_state import SentinelGraphState


def verification_node(
    verification_agent: VerificationAgent,
    verification_path: str,
):
    async def node(state: SentinelGraphState) -> dict:
        if state.get("error") is not None:
            return {"verification": None}

        incident = state.get("incident")
        if incident is not None and incident.status == IncidentStatus.INVESTIGATING:
            incident.begin_verification()

        verification = await verification_agent.verify(
            test_path=verification_path,
        )

        return {
            "verification": verification,
        }

    return node


def verification_router(
    state: SentinelGraphState,
    retry_policy: RepairRetryPolicy,
) -> str:
    if state.get("error") is not None:
        return "failure"

    verification = state.get("verification")

    if verification is None:
        return "failure"

    if verification.passed:
        return "complete"

    attempts = state.get("repair_attempts", ())

    if not retry_policy.can_retry(len(attempts)):
        return "failure"

    return "retry"


def create_verification_router(retry_policy: RepairRetryPolicy):
    def route(state: SentinelGraphState) -> str:
        return verification_router(state, retry_policy)

    return route
