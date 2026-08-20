from sentinel.tools.models import ToolRequest
from sentinel.tools.policy import ToolPolicy


def test_allowed_tool_id_permitted() -> None:
    policy = ToolPolicy(allowed_tools={"read_file"})

    request = ToolRequest(
        tool_name="read_file",
        arguments={"path": "README.md"},
    )

    assert policy.is_allowed(request)


def test_unapproved_tool_is_denied() -> None:
    policy = ToolPolicy(allowed_tools={"read_file"})

    request = ToolRequest(
        tool_name="write_file",
        arguments={"path": "README.md"},
    )

    assert not policy.is_allowed(request)
