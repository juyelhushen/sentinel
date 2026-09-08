from sentinel.agents.planner.prompt import build_planner_prompt
from sentinel.domain.models.incident import Incident


def test_build_planner_prompt() -> None:
    incident = Incident(
        title="Tests are failing",
        description="Tests started failing after a recent change.",
        repository="sentinel",
    )

    prompt = build_planner_prompt(incident)

    assert "Tests are failing" in prompt.user
    assert "Tests started failing after a recent change." in prompt.user
    assert "sentinel" in prompt.user
    assert "planning agent" in prompt.system
    assert "arguments" in prompt.system
    assert "search_code" in prompt.system
    assert '"query"' in prompt.system
    assert "inspect_file" in prompt.system
    assert '"path"' in prompt.system
    assert "run_tests" in prompt.system
    assert '"query": "example_function"' in prompt.user


def test_planner_prompt_describes_tool_arguments() -> None:
    incident = Incident(
        title="Authentication tests are failing",
        description="Token validation tests started failing.",
        repository="example-repository",
    )

    prompt = build_planner_prompt(incident)

    messages = prompt.to_message()

    content = "\n".join(
        message.content
        for message in messages
    )

    assert "inspect_file" in content
    assert "search_code" in content
    assert "run_tests" in content
    assert "analyze_logs" in content

    assert "arguments" in content
    assert '"path"' in content
    assert '"query"' in content
    assert '"test_path"' in content

    assert "Authentication tests are failing" in content
    assert "Token validation tests started failing." in content
    assert "example-repository" in content