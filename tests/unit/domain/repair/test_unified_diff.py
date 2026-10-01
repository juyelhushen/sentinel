import pytest

from sentinel.domain.repair.patch import PatchApplicationError
from sentinel.domain.repair.unified_diff import UnifiedDiffPatchApplier


def test_applies_single_line_replacement() -> None:
    original = (
        "def greet():\n"
        "    return 'hello'\n"
    )

    patch = (
        "--- a/example.py\n"
        "+++ b/example.py\n"
        "@@ -2,1 +2,1 @@\n"
        "-    return 'hello'\n"
        "+    return 'hello world'\n"
    )

    applier = UnifiedDiffPatchApplier()

    result = applier.apply(original, patch)

    assert result == (
        "def greet():\n"
        "    return 'hello world'\n"
    )


def test_applies_line_insertion() -> None:
    original = (
        "def greet():\n"
        "    return 'hello'\n"
    )

    patch = (
        "--- a/example.py\n"
        "+++ b/example.py\n"
        "@@ -1,2 +1,3 @@\n"
        " def greet():\n"
        "+    name = 'Sentinel'\n"
        "     return 'hello'\n"
    )

    applier = UnifiedDiffPatchApplier()

    result = applier.apply(original, patch)

    assert result == (
        "def greet():\n"
        "    name = 'Sentinel'\n"
        "    return 'hello'\n"
    )


def test_rejects_empty_patch() -> None:
    applier = UnifiedDiffPatchApplier()

    with pytest.raises(PatchApplicationError, match="empty"):
        applier.apply("hello\n", "")


def test_rejects_context_mismatch() -> None:
    original = "return 'hello'\n"

    patch = (
        "--- a/example.py\n"
        "+++ b/example.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-return 'different'\n"
        "+return 'fixed'\n"
    )

    applier = UnifiedDiffPatchApplier()

    with pytest.raises(PatchApplicationError, match="does not match"):
        applier.apply(original, patch)