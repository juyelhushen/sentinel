from sentinel.workflows.graph_state import SentinelGraphState


def verification_router(
    state: SentinelGraphState,
) -> str:
    verification = state.get("verification")

    if verification is None:
        return "failure"

    if verification.passed:
        return "complete"

    attempts = state.get(
        "repair_attempts",
        (),
    )

    if len(attempts) >= 3:
        return "failure"

    return "retry"