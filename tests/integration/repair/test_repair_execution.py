from pathlib import Path

import pytest

from sentinel.application.services.repair_execution_service import (
    RepairExecutionService,
)
from sentinel.application.tools.apply_patch import ApplyPatchTool
from sentinel.application.tools.local_gateway import LocalToolGateway
from sentinel.domain.repair import RepairPlan, RepairStep, RepairStepType
from sentinel.domain.repair.policy import RepairPolicy
from sentinel.domain.repair.unified_diff import UnifiedDiffPatchApplier
from sentinel.tools.executor import ToolExecutor
from sentinel.tools.policy import ToolPolicy
from sentinel.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_repair_execution_applies_patch(
    tmp_path: Path,
) -> None:
    # Arrange
    target = tmp_path / "example.py"

    target.write_text(
        "def greet():\n"
        "    return 'hello'\n",
        encoding="utf-8",
    )

    registry = ToolRegistry()

    registry.register(
        ApplyPatchTool(
            repository_root=tmp_path,
            repair_policy=RepairPolicy(tmp_path),
            patch_applier=UnifiedDiffPatchApplier(),
        )
    )

    policy = ToolPolicy(
        allowed_tools={"apply_patch"},
    )

    executor = ToolExecutor(
        registry=registry,
        policy=policy,
    )

    gateway = LocalToolGateway(
        executor=executor,
    )

    service = RepairExecutionService(
        tool_gateway=gateway,
    )

    repair_plan = RepairPlan(
        summary="Update greeting message.",
        steps=(
            RepairStep(
                step_number=1,
                action=RepairStepType.APPLY_PATCH,
                file_path="example.py",
                description="Change the greeting from hello to hello world.",
                patch=(
                    "--- a/example.py\n"
                    "+++ b/example.py\n"
                    "@@ -2,1 +2,1 @@\n"
                    "-    return 'hello'\n"
                    "+    return 'hello world'\n"
                ),
            ),
        ),
    )

    # Act
    results = await service.execute(repair_plan)

    # Assert
    assert len(results) == 1
    assert results[0].succeeded
    assert results[0].error is None

    assert target.read_text(encoding="utf-8") == (
        "def greet():\n"
        "    return 'hello world'\n"
    )