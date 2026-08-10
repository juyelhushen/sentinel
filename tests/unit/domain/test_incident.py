from sentinel.domain.enums.incident_status import IncidentStatus
from sentinel.domain.models.incident import Incident


def test_new_incident_is_created() -> None:
    incident = Incident(
        title="Login failure",
        description="Users cannot log in",
        repository="/workspace/sample-app",
    )

    assert incident.status == IncidentStatus.CREATED
    assert incident.executions == []


def test_incident_can_start_investigation() -> None:
    incident = Incident(
        title="Login failure",
        description="Users cannot log in",
        repository="/workspace/sample-app",
    )

    incident.start_investigation()

    assert incident.status == IncidentStatus.INVESTIGATING


def test_incident_can_fail() -> None:
    incident = Incident(
        title="Login failure",
        description="Users cannot log in",
        repository="/workspace/sample-app",
    )

    incident.fail()

    assert incident.status == IncidentStatus.FAILED
