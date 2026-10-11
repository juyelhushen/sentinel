from sentinel.workflows.graph_state import SentinelGraphState


def error_node(state: SentinelGraphState) -> SentinelGraphState:
    """Handle a workflow error"""

    return {
        "error": state["error"],
    }
