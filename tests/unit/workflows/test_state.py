from sentinel.agents.planner.models import InvestigationPlan, PlanStep, PlanStepType
from sentinel.domain.models.incident import Incident
from sentinel.workflows.state import SentinelState


def test_sentinel_state_initializes_without_plan() -> None:
    incident: Incident = Incident(
        title="Tests are failing",
        description="Tests started failing after a recent change.",
        repository="sentinel",
    )

    state = SentinelState(incident=incident)

    assert state.incident == incident
    assert state.plan is None
    assert state.error is None


def test_sentinel_state_can_store_plan() -> None:
    incident = Incident(
        title="Tests are failing",
        description="Several tests are failing.",
        repository="sentinel",
    )

    plan = InvestigationPlan(
        summary="Investigate failing tests.",
        steps=(
            PlanStep(
                step_number=1,
                action=PlanStepType.RUN_TESTS,
                description="Run the test suite.",
            ),
        ),
    )

    state = SentinelState(
        incident=incident,
        plan=plan,
    )

    assert state.plan == plan
    assert len(state.plan.steps) == 1
