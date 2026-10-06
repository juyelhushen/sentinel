from sentinel.application.ports.tool_gateway import ToolGateway
from sentinel.domain.models.verification import VerificationResult, VerificationStatus
from sentinel.tools.models import ToolRequest


class VerificationAgent:
    def __init__(self, tool_gateway : ToolGateway) -> None:
        self._tool_gateway = tool_gateway

    async def verify(
        self,
        test_path: str,
    ) -> VerificationResult:
        request = ToolRequest(
            tool_name="run_tests",
            arguments={
                "path": test_path,
            },
        )

        result = await self._tool_gateway.execute(request)

        output = str(result.output or result.error or "")

        if result.succeeded:
            return VerificationResult(
                status=VerificationStatus.PASSED,
                summary="Verification tests passed.",
                test_output=output,
            )

        return VerificationResult(
            status=VerificationStatus.FAILED,
            summary="Verification tests failed.",
            test_output=output,
        )