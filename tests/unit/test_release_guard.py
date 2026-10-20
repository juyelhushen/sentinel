import json
from types import SimpleNamespace

import pytest

from scripts.release_guard import (
    ReleaseGuardError,
    parse_deploy_page,
    parse_hook_response,
    required_configuration,
    validate_commit_reachable,
    validate_health_response,
    validate_release_context,
    validate_release_tag,
)


def test_validate_release_context_accepts_matching_stable_tag() -> None:
    assert (
        validate_release_context("push", "tag", "v0.3.0", "0.3.0", "0.3.0") == "0.3.0"
    )


@pytest.mark.parametrize(
    "tag",
    (
        "v01.3.0",
        "v0.03.0",
        "v0.3.00",
        "v0.3",
        "v0.3.0-rc.1",
        "v0.3.0+build.1",
        "0.3.0",
    ),
)
def test_validate_release_tag_rejects_noncanonical_tags(tag: str) -> None:
    with pytest.raises(ReleaseGuardError):
        validate_release_tag(tag, "0.3.0", "0.3.0")


def test_validate_release_context_rejects_mismatched_versions() -> None:
    with pytest.raises(ReleaseGuardError, match="must match"):
        validate_release_context("push", "tag", "v0.3.0", "0.3.0", "0.1.0")


def test_validate_release_context_rejects_project_version_mismatch() -> None:
    with pytest.raises(ReleaseGuardError, match="must match"):
        validate_release_context("push", "tag", "v0.3.0", "0.2.0", "0.3.0")


def test_validate_release_context_rejects_non_tag_events() -> None:
    with pytest.raises(ReleaseGuardError, match="pushed tags"):
        validate_release_context("pull_request", "branch", "v0.3.0", "0.3.0", "0.3.0")


def test_validate_commit_reachable_fetches_origin_main_before_check() -> None:
    commit_sha = "a" * 40
    commands: list[list[str]] = []
    return_codes = [0, 0]

    def run_command(command: list[str], **kwargs: object) -> SimpleNamespace:
        commands.append(command)
        return SimpleNamespace(returncode=return_codes.pop(0))

    validate_commit_reachable(commit_sha, run_command)

    assert commands == [
        [
            "git",
            "fetch",
            "--no-tags",
            "origin",
            "+refs/heads/main:refs/remotes/origin/main",
        ],
        [
            "git",
            "merge-base",
            "--is-ancestor",
            commit_sha,
            "refs/remotes/origin/main",
        ],
    ]


def test_validate_commit_reachable_rejects_non_ancestor() -> None:
    return_codes = [0, 1]

    def run_command(command: list[str], **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=return_codes.pop(0))

    with pytest.raises(ReleaseGuardError, match="not reachable"):
        validate_commit_reachable("a" * 40, run_command)


def test_validate_commit_reachable_rejects_unavailable_origin_main() -> None:
    commands: list[list[str]] = []

    def run_command(command: list[str], **kwargs: object) -> SimpleNamespace:
        commands.append(command)
        return SimpleNamespace(returncode=128)

    with pytest.raises(ReleaseGuardError, match="fetch origin/main"):
        validate_commit_reachable("a" * 40, run_command)
    assert len(commands) == 1


def test_validate_commit_reachable_rejects_incomplete_git_history() -> None:
    return_codes = [0, 128]

    def run_command(command: list[str], **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=return_codes.pop(0))

    with pytest.raises(ReleaseGuardError, match="history may be incomplete"):
        validate_commit_reachable("a" * 40, run_command)


def test_required_configuration_rejects_missing_render_values(monkeypatch) -> None:
    for name in (
        "RENDER_API_KEY",
        "RENDER_DEPLOY_HOOK_URL",
        "RENDER_SERVICE_ID",
        "GITHUB_SHA",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ReleaseGuardError, match="RENDER_API_KEY"):
        required_configuration()


def test_required_configuration_rejects_hook_for_different_service(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_API_KEY", "test-api-key")
    monkeypatch.setenv(
        "RENDER_DEPLOY_HOOK_URL",
        "https://api.render.com/deploy/srv-other?key=test-hook-key",
    )
    monkeypatch.setenv("RENDER_SERVICE_ID", "srv-sentinel")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)

    with pytest.raises(ReleaseGuardError, match="RENDER_SERVICE_ID"):
        required_configuration()


def test_required_configuration_rejects_empty_deploy_hook_key(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_API_KEY", "test-api-key")
    monkeypatch.setenv(
        "RENDER_DEPLOY_HOOK_URL",
        "https://api.render.com/deploy/srv-sentinel?key=",
    )
    monkeypatch.setenv("RENDER_SERVICE_ID", "srv-sentinel")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)

    with pytest.raises(ReleaseGuardError, match="Render hook"):
        required_configuration()


def test_parse_deploy_page_matches_render_cursor_wrapper() -> None:
    page = parse_deploy_page(
        [{"deploy": {"id": "dep-123", "status": "live"}, "cursor": "cursor-1"}]
    )

    assert page == [({"id": "dep-123", "status": "live"}, "cursor-1")]


def test_parse_deploy_page_rejects_malformed_response() -> None:
    with pytest.raises(ReleaseGuardError, match="malformed"):
        parse_deploy_page([{"deploy": {"id": "dep-123"}}])


def test_parse_hook_response_extracts_render_deploy_id() -> None:
    assert parse_hook_response(200, b'{"deploy":{"id":"dep-123"}}') == "dep-123"


def test_parse_hook_response_accepts_queued_response_without_id() -> None:
    assert parse_hook_response(202, b'{"message":"queued"}') is None


def test_parse_hook_response_rejects_unexpected_queued_deploy_id() -> None:
    with pytest.raises(ReleaseGuardError, match="must not include a deployment ID"):
        parse_hook_response(202, b'{"deploy":{"id":"dep-old"}}')


def test_parse_hook_response_rejects_malformed_success() -> None:
    with pytest.raises(ReleaseGuardError, match="malformed"):
        parse_hook_response(200, b'{"deploy":{}}')


@pytest.mark.parametrize(
    ("path", "body"),
    (
        ("/health", {"status": "ok", "service": "sentinel"}),
        ("/health/ready", {"status": "ready", "database": "ok"}),
    ),
)
def test_validate_health_response_checks_expected_fields(
    path: str, body: dict[str, str]
) -> None:
    validate_health_response(path, 200, json.dumps(body).encode())


def test_validate_health_response_rejects_wrong_fields() -> None:
    with pytest.raises(ReleaseGuardError, match="health contract"):
        validate_health_response("/health/ready", 200, b'{"status":"ready"}')
