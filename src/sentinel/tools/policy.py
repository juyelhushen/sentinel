from sentinel.tools.models import ToolRequest


class ToolPolicy:
    """Controls which tools Sentinel is allowed to execute."""

    def __init__(self, allowed_tools: set[str]) -> None:
        self._allowed_tools = allowed_tools

    def is_allowed(self, request: ToolRequest) -> bool:
        """Return whether the requested tool is allowed."""

        return request.tool_name in self._allowed_tools
