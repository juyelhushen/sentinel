from sentinel.domain.models.incident import Incident
from sentinel.workflows.routing import route_after_planning


def test_route_after_planning_returns_end_on_success() -> None:
    incident = Incident(
        title="Tests are failing",
        description="Several tests are failing.",
        repository="sentinel",
    )

    result = route_after_planning(
        {
            "incident": incident,
            "plan": None,
            "error": None,
        }
    )

    assert result == "end"

def test_route_after_planning_returns_error_on_failure() -> None:
    incident = Incident(
    title="Tests are failing",
    description="Several tests are failing.",
    repository="sentinel",
    )

    result = route_after_planning(
        {
            "incident": incident,
            "plan": None,
            "error": "LLM unavailable",
        }
    )

    assert result == "error"
