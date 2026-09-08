from sentinel.workflows.graph_state import SentinelGraphState


def route_after_planning(
        state: SentinelGraphState
) -> str:
    """Determine where the workflow goes after planning"""

    if state["error"] is not None:
        return "error";

    return "investigator";