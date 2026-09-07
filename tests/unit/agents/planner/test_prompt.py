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