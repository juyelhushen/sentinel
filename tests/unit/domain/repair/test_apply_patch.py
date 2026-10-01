from pathlib import Path

import pytest

from sentinel.application.tools.apply_patch import ApplyPatchTool
from sentinel.domain.repair.policy import RepairPolicy
from sentinel.domain.repair.unified_diff import UnifiedDiffPatchApplier
from sentinel.tools.models import ToolRequest


@pytest.mark.asyncio
async def test_apply_patch_modifies_repository_file(
    tmp_path: Path,
) -> None:
    target = tmp_path / "example.py"
    target.write_text(
        "def greet():\n"
        "    return 'hello'\n",
        encoding="utf-8",
    )

    tool = ApplyPatchTool(
        repository_root=tmp_path,
        repair_policy=RepairPolicy(tmp_path),
        patch_applier=UnifiedDiffPatchApplier(),
    )

    request = ToolRequest(
        tool_name="apply_patch",
        arguments={
            "file_path": "example.py",
            "patch": (
                "--- a/example.py\n"
                "+++ b/example.py\n"
                "@@ -2,1 +2,1 @@\n"
                "-    return 'hello'\n"
                "+    return 'hello world'\n"
            ),
        },
    )

    result = await tool.execute(request)

    assert result.succeeded
    assert target.read_text(encoding="utf-8") == (
        "def greet():\n"
        "    return 'hello world'\n"
    )


@pytest.mark.asyncio
async def test_apply_patch_denies_path_traversal(
    tmp_path: Path,
) -> None:
    tool = ApplyPatchTool(
        repository_root=tmp_path,
        repair_policy=RepairPolicy(tmp_path),
        patch_applier=UnifiedDiffPatchApplier(),
    )

    request = ToolRequest(
        tool_name="apply_patch",
        arguments={
            "file_path": "../outside.py",
            "patch": "invalid",
        },
    )

    result = await tool.execute(request)

    assert result.status.value == "denied"