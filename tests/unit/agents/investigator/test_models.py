from sentinel.agents.investigator.models import (
    StepInvestigationResult,
    InvestigationResult,
)
from sentinel.agents.planner.models import PlanStepType

def test_step_investigation() -> None:
    result= StepInvestigationResult(
        step_number=1,
        action=PlanStepType.RUN_TESTS,
        success=True,
        findings="All tests completed successfully.",
    )

    assert result.step_number == 1
    assert result.action == PlanStepType.RUN_TESTS
    assert result.success is True
    assert result.findings == "All tests completed successfully."
    
def test_investigation_result() -> None:
    step_result =StepInvestigationResult(
        step_number=1,
        action=PlanStepType.RUN_TESTS,
        success=True,
        findings="Tests completed",
    )
    
    result = InvestigationResult(
        summary="Investigation completed.",
        step_results=(step_result,),
    )
    
    assert result.summary == "Investigation completed."
    assert len(result.step_results) == 1
    assert result.step_results[0] == step_result

