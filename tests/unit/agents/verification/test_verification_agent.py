import pytest

from sentinel.agents.verification.verification_agent import VerificationAgent
from sentinel.application.ports.tool_gateway import ToolGateway
from sentinel.domain.models.verification import VerificationStatus
from sentinel.tools.models import ToolExecutionStatus, ToolResult


class FakeToolGateway(ToolGateway):
    def __init__(self, result: ToolResult) -> None:
        self.result = result
        self.requests = []

    async def execute(self, request):
        self.requests.append(request)
        return self.result


@pytest.mark.asyncio
async def test_verification_passes_when_tests_succeed() -> None:
    gateway = FakeToolGateway(
        ToolResult(
            status=ToolExecutionStatus.SUCCESS,
            output="3 passed in 0.12s",
        )
    )

    agent = VerificationAgent(
        tool_gateway=gateway,
    )

    result = await agent.verify(
        test_path="tests/test_order.py",
    )

    assert result.status == VerificationStatus.PASSED
    assert result.passed
    assert "3 passed" in result.test_output

    assert len(gateway.requests) == 1
    assert gateway.requests[0].tool_name == "run_tests"
    assert (
        gateway.requests[0].arguments["path"]
        == "tests/test_order.py"
    )


@pytest.mark.asyncio
async def test_verification_fails_when_tests_fail() -> None:
    gateway = FakeToolGateway(
        ToolResult(
            status=ToolExecutionStatus.FAILURE,
            output="1 failed, 2 passed",
            error="pytest returned exit code 1",
        )
    )

    agent = VerificationAgent(
        tool_gateway=gateway,
    )

    result = await agent.verify(
        test_path="tests/test_order.py",
    )

    assert result.status == VerificationStatus.FAILED
    assert not result.passed
    assert "1 failed" in result.test_output



@pytest.mark.asyncio
async def test_verification_preserves_tool_error() -> None:
    gateway = FakeToolGateway(
        ToolResult(
            status=ToolExecutionStatus.FAILURE,
            error="Test runner could not start.",
        )
    )

    agent = VerificationAgent(
        tool_gateway=gateway,
    )

    result = await agent.verify(
        test_path="tests/test_order.py",
    )

    assert result.status == VerificationStatus.FAILED
    assert "Test runner could not start." in result.test_output