from unittest.mock import AsyncMock, Mock

import pytest
from mcp.shared.exceptions import MCPError

from sentinel.infrastructure.mcp.tool_gateway import MCPToolGateway
from sentinel.tools.models import ToolExecutionStatus, ToolRequest


@pytest.mark.asyncio
async def test_initialize_discovers_tools() -> None:
    client = AsyncMock()
    client.list_tools.return_value = (
        Mock(name="read_file"),
        Mock(name="search_code"),
    )
    client.tool_names = frozenset({"read_file", "search_code"})

    gateway = MCPToolGateway(client)

    await gateway.initialize()

    client.list_tools.assert_awaited_once()
    assert client.tool_names == frozenset({"read_file", "search_code"})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [MCPError(-32000, "connection lost"), TimeoutError("connection lost")],
)
async def test_execute_returns_failure_when_mcp_client_raises(error: Exception) -> None:

    client = Mock()
    client.tool_names = {"read_file"}
    client.call_tool = AsyncMock(side_effect=error)

    gateway = MCPToolGateway(client)

    request = ToolRequest(
        tool_name="read_file",
        arguments={"path": "example.txt"},
    )

    result = await gateway.execute(request)

    assert result.status == ToolExecutionStatus.FAILURE
    assert result.error is not None
    assert "connection lost" in result.error
    assert result.request_id == request.request_id

    client.call_tool.assert_awaited_once_with(
        "read_file",
        {"path": "example.txt"},
    )


@pytest.mark.asyncio
async def test_execute_preserves_explicit_denial() -> None:
    class DeniedResult:
        is_error = True

        def __init__(self) -> None:
            self.content = [
                type(
                    "Item", (), {"text": "[DENIED] Tool execution denied: read_file"}
                )()
            ]

    client = Mock()
    client.tool_names = {"read_file"}
    client.call_tool = AsyncMock(return_value=DeniedResult())

    gateway = MCPToolGateway(client)

    result = await gateway.execute(
        ToolRequest(
            tool_name="read_file",
            arguments={"path": "example.txt"},
        )
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert result.error.startswith("[DENIED]")


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [TypeError, RuntimeError])
async def test_execute_propagates_unexpected_errors(
    error_type: type[Exception],
) -> None:
    client = Mock()
    client.tool_names = {"read_file"}
    client.call_tool = AsyncMock(
        side_effect=error_type("invalid client implementation")
    )

    gateway = MCPToolGateway(client)

    with pytest.raises(error_type, match="invalid client implementation"):
        await gateway.execute(ToolRequest(tool_name="read_file", arguments={}))
