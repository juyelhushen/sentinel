from unittest.mock import AsyncMock

import pytest

from sentinel.agents.verification.verification_agent import VerificationAgent
from sentinel.domain.models.verification import VerificationResult, VerificationStatus
from sentinel.workflows.graph_state import SentinelGraphState
from sentinel.workflows.nodes.verification import verification_node


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [VerificationStatus.PASSED, VerificationStatus.FAILED])
async def test_verification_node_invokes_agent(status: VerificationStatus) -> None:
    verification = VerificationResult(
        status=status,
        summary="Verification finished",
        test_output="pytest output",
    )
    agent = AsyncMock(spec=VerificationAgent)
    agent.verify.return_value = verification
    node = verification_node(agent, "tests/test_order.py")
    assert callable(node)
    state: SentinelGraphState = {"error": None}

    result = await node(state)

    agent.verify.assert_awaited_once_with(test_path="tests/test_order.py")
    assert result == {"verification": verification}
    assert "verification" not in state


@pytest.mark.asyncio
async def test_verification_node_skips_existing_error_and_clears_stale_result() -> None:
    agent = AsyncMock(spec=VerificationAgent)
    state: SentinelGraphState = {
        "error": "Repair execution failed.",
        "verification": VerificationResult(
            status=VerificationStatus.PASSED,
            summary="Previous verification passed",
            test_output="3 passed",
        ),
    }

    result = await verification_node(agent, "tests")(state)

    agent.verify.assert_not_awaited()
    assert result == {"verification": None}
    assert state["error"] == "Repair execution failed."