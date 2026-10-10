from pathlib import Path

import pytest

from sentinel.domain.repair.policy import RepairPolicy


@pytest.fixture
def repository_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def policy(repository_root: Path) -> RepairPolicy:
    return RepairPolicy(repository_root)


def test_allows_repository_relative_file(
    repository_root: Path,
    policy: RepairPolicy,
) -> None:
    result = policy.validate_path("src/service.py")

    assert result == repository_root / "src/service.py"


def test_rejects_absolute_path(policy: RepairPolicy) -> None:
    with pytest.raises(ValueError, match="repository-relative"):
        policy.validate_path("/etc/passwd")


def test_rejects_path_traversal(
    policy: RepairPolicy,
) -> None:
    with pytest.raises(ValueError, match="inside the repository"):
        policy.validate_path("../outside.txt")


def test_rejects_nested_path_traversal(
    policy: RepairPolicy,
) -> None:
    with pytest.raises(ValueError, match="inside the repository"):
        policy.validate_path("src/../../outside.txt")


def test_rejects_git_directory(
    policy: RepairPolicy,
) -> None:
    with pytest.raises(
        ValueError,
        match="protected directories",
    ):
        policy.validate_path(".git/config")


def test_rejects_nested_git_directory(
    policy: RepairPolicy,
) -> None:
    with pytest.raises(
        ValueError,
        match="protected directories",
    ):
        policy.validate_path("some/path/.git/config")


def test_rejects_env_file(
    policy: RepairPolicy,
) -> None:
    with pytest.raises(
        ValueError,
        match="protected files",
    ):
        policy.validate_path(".env")


def test_rejects_nested_env_file(
    policy: RepairPolicy,
) -> None:
    with pytest.raises(
        ValueError,
        match="protected files",
    ):
        policy.validate_path("config/.env")


def test_rejects_symlink_outside_repository(policy: RepairPolicy, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    link = tmp_path / "linked.txt"

    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Symlinks are not available in this environment.")

    with pytest.raises(ValueError, match="inside the repository"):
        policy.validate_path("linked.txt")