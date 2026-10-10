
from pathlib import Path

import pytest
from sentinel.application.tools.apply_patch import ApplyPatchTool
from sentinel.domain.repair.policy import RepairPolicy
from sentinel.domain.repair.unified_diff import UnifiedDiffPatchApplier
from sentinel.tools.models import ToolRequest


@pytest.mark.asyncio
async def test_invalid_patch_does_not_modify_file(
    tmp_path: Path,
) -> None:
    target = tmp_path / "example.py"
    original = "def greet():\n    return 'hello'\n"
    target.write_text(original, encoding="utf-8")

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
                "-    return 'wrong'\n"
                "+    return 'modified'\n"
            ),
        },
    )

    result = await tool.execute(request)

    assert not result.succeeded
    assert target.read_text(encoding="utf-8") == original
