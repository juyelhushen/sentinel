from sentinel.agents.planner.models import InvestigationPlan, PlanStep, PlanStepType


def test_investigation_plan_contains_steps() -> None:
    step = PlanStep(
        step_number=1,
        action=PlanStepType.RUN_TESTS,
        description="Run the failing test suite.",
    )

    plan = InvestigationPlan(
        summary="Investigate failing tests.",
        steps=(step,),
    )

    assert plan.summary == "Investigate failing tests."
    assert len(plan.steps) == 1
    assert plan.steps[0].action == PlanStepType.RUN_TESTS


def test_plan_step_defaults_to_empty_arguments() -> None:
    step = PlanStep(
        step_number=1,
        action=PlanStepType.SEARCH_CODE,
        description="Search authentication code.",
    )

    assert step.arguments == {}


def test_plan_step_stores_arguments() -> None:
    step = PlanStep(
        step_number=1,
        action=PlanStepType.SEARCH_CODE,
        description="Search authentication code.",
        arguments={
            "query": "validate_token",
        },
    )

    assert step.arguments == {
        "query": "validate_token",
    }