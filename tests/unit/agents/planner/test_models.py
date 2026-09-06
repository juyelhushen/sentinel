from sentinel.agents.planner.models import PlanStep, PlanStepType, InvestigationPlan


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