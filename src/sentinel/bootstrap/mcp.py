from sentinel.infrastructure.mcp.client import SentinelMCPClient
from sentinel.infrastructure.mcp.tool_gateway import MCPToolGateway


async def create_mcp_tool_gateway(
        command: str,
        args: list[str],
) -> tuple[SentinelMCPClient, MCPToolGateway]:
    client = SentinelMCPClient()

    await client.connect(
        command=command,
        args=args,
    )

    gateway = MCPToolGateway(client)

    return client, gateway