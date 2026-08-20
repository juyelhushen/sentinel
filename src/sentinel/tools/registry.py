from sentinel.tools.base import Tool


class ToolRegistry:
    """Registry of tools available to Sentinel."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""

        if tool.name in self._tools:
            raise ValueError(f"Tool already registered with name {tool.name}. ")

        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        """Retrieve a registered tool."""

        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Tool not found: {name}. ") from exc

    def contains(self, name: str) -> bool:
        """Return whether the tool is registered."""

        return name in self._tools

    def list_tools(self) -> list[Tool]:
        """Return a list of all registered tools."""

        return list(self._tools.values())
