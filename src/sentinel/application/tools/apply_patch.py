from pathlib import Path

from sentinel.domain.repair.patch import PatchApplier, PatchApplicationError
from sentinel.domain.repair.policy import RepairPolicy
from sentinel.tools.base import Tool
from sentinel.tools.models import ToolRequest, ToolResult, ToolExecutionStatus


class ApplyPatchTool(Tool):
    def __init__(
        self,
        repository_root: Path,
        repair_policy: RepairPolicy,
        patch_applier: PatchApplier,
    ) -> None:
        self._repository_root = repository_root
        self._repair_policy = repair_policy
        self._patch_applier = patch_applier

    @property
    def name(self) -> str:
        return "apply_patch"

    @property
    def description(self) -> str:
        return (
            "Safely applies a unified diff patch to an existing "
            "repository file."
        )

    async def execute(self, request: ToolRequest) -> ToolResult:
        file_path = request.arguments.get("file_path")
        patch = request.arguments.get("patch")

        if not isinstance(file_path, str):
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error="file_path must be a string.",
                request_id=request.request_id,
            )

        if not isinstance(patch, str):
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error="patch must be a string.",
                request_id=request.request_id,
            )

        try:
            target_path = self._repair_policy.validate_path(file_path)
        except ValueError as exc:
            return ToolResult(
                status=ToolExecutionStatus.DENIED,
                error=str(exc),
                request_id=request.request_id,
            )

        if not target_path.exists():
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=f"File does not exist: {file_path}",
                request_id=request.request_id,
            )

        if not target_path.is_file():
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=f"Target is not a file: {file_path}",
                request_id=request.request_id,
            )

        try:
            original = target_path.read_text(encoding="utf-8")
            modified = self._patch_applier.apply(original, patch)
            target_path.write_text(modified, encoding="utf-8")
        except UnicodeDecodeError as exc:
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=f"File is not valid UTF-8: {file_path}",
                request_id=request.request_id,
            )
        except PatchApplicationError as exc:
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=str(exc),
                request_id=request.request_id,
            )
        except OSError as exc:
            return ToolResult(
                status=ToolExecutionStatus.FAILURE,
                error=f"Unable to modify file: {exc}",
                request_id=request.request_id,
            )

        return ToolResult(
            status=ToolExecutionStatus.SUCCESS,
            output=f"Patch applied successfully to {file_path}.",
            request_id=request.request_id,
        )