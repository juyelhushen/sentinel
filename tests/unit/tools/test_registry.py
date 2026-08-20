import pytest

from sentinel.tools.base import Tool
from sentinel.tools.registry import ToolRegistry


class FakeTool(Tool):
    @property
    def name(self) -> str:
        return "Fake_tool"

    @property
    def description(self) -> str:
        return "Fake tool for testing."

    async def execute(self, request):
        raise NotImplementedError

    def test_register_and_get_tool(self) -> None:
        registry = ToolRegistry()
        tool = FakeTool()

        registry.register(tool)

        assert registry.get("fake_tool") is tool

    def test_duplicate_tool_registration_is_rejected(self) -> None:
        registry = ToolRegistry()
        tool = FakeTool()

        registry.register(tool)

        with pytest.raises(ValueError):
            registry.register(tool)

    def test_contains_returns_correct_result(self) -> None:
        registry = ToolRegistry()

        assert not registry.contains("fake_tool")

        registry.register(FakeTool())

        assert registry.contains("fake_tool")
