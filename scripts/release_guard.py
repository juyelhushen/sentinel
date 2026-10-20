"""Validate release tags and verify the Render deployment they trigger."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import tomllib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

RENDER_API_ROOT = "https://api.render.com/v1"
PUBLIC_API_ROOT = "https://sentinel-api-6jrt.onrender.com"
MAX_RESPONSE_BYTES = 1_000_000
MAX_LIST_PAGES = 10
LIST_PAGE_SIZE = 100
REQUEST_TIMEOUT_SECONDS = 30
DEPLOY_TIMEOUT_SECONDS = 15 * 60
DEPLOY_POLL_INTERVAL_SECONDS = 15
HEALTH_TIMEOUT_SECONDS = 120
HEALTH_POLL_INTERVAL_SECONDS = 5
HEALTH_REQUEST_TIMEOUT_SECONDS = 10
TAG_PATTERN = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
IN_PROGRESS_STATUSES = {
    "created",
    "queued",
    "build_in_progress",
    "update_in_progress",
    "pre_deploy_in_progress",
}
FAILED_STATUSES = {
    "deactivated",
    "build_failed",
    "update_failed",
    "canceled",
    "pre_deploy_failed",
}
HEALTH_ENDPOINTS = (
    ("/health", {"status": "ok", "service": "sentinel"}),
    ("/health/ready", {"status": "ready", "database": "ok"}),
)


class ReleaseGuardError(Exception):
    """A sanitized release validation or deployment verification failure."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        return None


def validate_release_tag(tag: str, project_version: str, package_version: str) -> str:
    match = TAG_PATTERN.fullmatch(tag)
    if match is None:
        raise ReleaseGuardError(
            "Release tag must use stable vMAJOR.MINOR.PATCH syntax without leading zeroes."
        )

    tag_version = ".".join(match.groups())
    if tag_version != project_version or tag_version != package_version:
        raise ReleaseGuardError(
            "Release tag, project version, and sentinel.__version__ must match."
        )
    return tag_version


def validate_release_context(
    event_name: str,
    ref_type: str,
    tag: str,
    project_version: str,
    package_version: str,
) -> str:
    if event_name != "push" or ref_type != "tag":
        raise ReleaseGuardError("Release deployment is allowed only for pushed tags.")
    return validate_release_tag(tag, project_version, package_version)


def validate_commit_reachable(
    commit_sha: str, run_command: Callable[..., Any] | None = None
) -> None:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit_sha):
        raise ReleaseGuardError("GITHUB_SHA is not a full commit SHA.")

    command_runner = subprocess.run if run_command is None else run_command
    fetch_command = [
        "git",
        "fetch",
        "--no-tags",
        "origin",
        "+refs/heads/main:refs/remotes/origin/main",
    ]
    try:
        fetch_result = command_runner(
            fetch_command, check=False, capture_output=True, text=True
        )
    except OSError:
        raise ReleaseGuardError(
            "Could not fetch origin/main for release validation."
        ) from None
    if fetch_result.returncode != 0:
        raise ReleaseGuardError("Could not fetch origin/main for release validation.")

    ancestry_command = [
        "git",
        "merge-base",
        "--is-ancestor",
        commit_sha,
        "refs/remotes/origin/main",
    ]
    try:
        ancestry_result = command_runner(
            ancestry_command, check=False, capture_output=True, text=True
        )
    except OSError:
        raise ReleaseGuardError(
            "Could not verify release commit against origin/main."
        ) from None
    if ancestry_result.returncode == 1:
        raise ReleaseGuardError("Release tag commit is not reachable from origin/main.")
    if ancestry_result.returncode != 0:
        raise ReleaseGuardError(
            "Could not verify release commit against origin/main; Git history may be incomplete."
        )


def parse_deploy_page(payload: Any) -> list[tuple[dict[str, Any], str]]:
    if not isinstance(payload, list):
        raise ReleaseGuardError("Render deploy-list response was malformed.")

    parsed: list[tuple[dict[str, Any], str]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise ReleaseGuardError("Render deploy-list response was malformed.")
        deploy = entry.get("deploy")
        cursor = entry.get("cursor")
        if (
            not isinstance(deploy, dict)
            or not isinstance(deploy.get("id"), str)
            or not deploy["id"]
            or not isinstance(cursor, str)
            or not cursor
        ):
            raise ReleaseGuardError("Render deploy-list response was malformed.")
        parsed.append((deploy, cursor))
    return parsed


def parse_hook_response(status_code: int, body: bytes) -> str | None:
    if status_code not in {200, 202}:
        raise ReleaseGuardError(f"Render deploy hook returned HTTP {status_code}.")

    if status_code == 200:
        payload = decode_json(body, "Render deploy-hook response")
        if not isinstance(payload, dict):
            raise ReleaseGuardError("Render deploy-hook response was malformed.")
        deploy = payload.get("deploy")
        if not isinstance(deploy, dict):
            raise ReleaseGuardError("Render deploy-hook response was malformed.")
        deploy_id = deploy.get("id")
        if not isinstance(deploy_id, str) or not deploy_id:
            raise ReleaseGuardError("Render deploy-hook response was malformed.")
        return deploy_id

    if not body.strip():
        return None
    payload = decode_json(body, "Render queued deploy-hook response")
    if not isinstance(payload, dict):
        raise ReleaseGuardError("Render queued deploy-hook response was malformed.")
    deploy = payload.get("deploy")
    if deploy is None:
        return None
    if not isinstance(deploy, dict):
        raise ReleaseGuardError("Render queued deploy-hook response was malformed.")
    if "id" in deploy:
        raise ReleaseGuardError(
            "Render queued deploy-hook response must not include a deployment ID."
        )
    return None


def validate_health_response(path: str, status_code: int, body: bytes) -> None:
    if status_code != 200:
        raise ReleaseGuardError(f"Public {path} returned HTTP {status_code}.")
    payload = decode_json(body, f"Public {path} response")
    if not isinstance(payload, dict):
        raise ReleaseGuardError(f"Public {path} response was malformed.")

    expected = dict(HEALTH_ENDPOINTS)[path]
    if any(payload.get(field) != value for field, value in expected.items()):
        raise ReleaseGuardError(
            f"Public {path} response did not match its health contract."
        )


def decode_json(body: bytes, label: str) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except UnicodeDecodeError, json.JSONDecodeError:
        raise ReleaseGuardError(f"{label} was not valid JSON.") from None


def request_bytes(
    url: str,
    *,
    method: str,
    label: str,
    headers: dict[str, str] | None = None,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> tuple[int, bytes]:
    request = Request(url, headers=headers or {}, method=method)
    opener = build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            status_code = response.status
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        status_code = error.code
        body = b""
    except URLError, TimeoutError, OSError, ValueError:
        raise ReleaseGuardError(f"{label} request failed or timed out.") from None

    if len(body) > MAX_RESPONSE_BYTES:
        raise ReleaseGuardError(f"{label} response exceeded the allowed size.")
    return status_code, body


def required_configuration() -> tuple[str, str, str, str]:
    names = (
        "RENDER_API_KEY",
        "RENDER_DEPLOY_HOOK_URL",
        "RENDER_SERVICE_ID",
        "GITHUB_SHA",
    )
    missing = [name for name in names if not os.environ.get(name, "").strip()]
    if missing:
        raise ReleaseGuardError(
            "Required deployment configuration is missing: " + ", ".join(missing) + "."
        )

    api_key = os.environ["RENDER_API_KEY"].strip()
    hook_url = os.environ["RENDER_DEPLOY_HOOK_URL"].strip()
    service_id = os.environ["RENDER_SERVICE_ID"].strip()
    commit_sha = os.environ["GITHUB_SHA"].strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit_sha):
        raise ReleaseGuardError("GITHUB_SHA is not a full commit SHA.")
    validate_deploy_hook_url(hook_url, service_id)

    return api_key, hook_url, service_id, commit_sha


def render_json(
    path: str,
    *,
    api_key: str,
    label: str,
    query: list[tuple[str, str]] | None = None,
) -> Any:
    url = f"{RENDER_API_ROOT}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    status_code, body = request_bytes(
        url,
        method="GET",
        label=label,
        headers={"Accept": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    if status_code != 200:
        raise ReleaseGuardError(f"{label} returned HTTP {status_code}.")
    return decode_json(body, label)


def validate_deploy_hook_url(hook_url: str, service_id: str) -> None:
    try:
        parsed_hook = urlsplit(hook_url)
        hook_keys = [
            value for key, value in parse_qsl(parsed_hook.query) if key == "key"
        ]
    except ValueError:
        raise ReleaseGuardError("RENDER_DEPLOY_HOOK_URL is invalid.") from None
    hook_service_id = unquote(parsed_hook.path.removeprefix("/deploy/"))
    if (
        parsed_hook.scheme != "https"
        or parsed_hook.hostname != "api.render.com"
        or not parsed_hook.path.startswith("/deploy/")
        or not hook_service_id
        or hook_service_id != service_id
        or parsed_hook.fragment
        or len(hook_keys) != 1
        or not hook_keys[0]
    ):
        raise ReleaseGuardError(
            "RENDER_DEPLOY_HOOK_URL must be a Render hook for RENDER_SERVICE_ID."
        )


def list_deploys(
    service_id: str, api_key: str, created_after: str
) -> list[dict[str, Any]]:
    service_path = f"/services/{quote(service_id, safe='')}/deploys"
    deploys: list[dict[str, Any]] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()

    for _ in range(MAX_LIST_PAGES):
        query = [("limit", str(LIST_PAGE_SIZE)), ("createdAfter", created_after)]
        if cursor is not None:
            query.append(("cursor", cursor))
        payload = render_json(
            service_path,
            api_key=api_key,
            label="Render deploy-list response",
            query=query,
        )
        page = parse_deploy_page(payload)
        deploys.extend(deploy for deploy, _ in page)
        if len(page) < LIST_PAGE_SIZE:
            return deploys

        next_cursor = page[-1][1]
        if next_cursor in seen_cursors:
            raise ReleaseGuardError("Render deploy-list pagination repeated a cursor.")
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    raise ReleaseGuardError("Render deploy-list pagination exceeded its safety bound.")


def deploy_commit_id(deploy: dict[str, Any]) -> str | None:
    commit = deploy.get("commit")
    if commit is None:
        return None
    if not isinstance(commit, dict):
        raise ReleaseGuardError("Render deploy response was malformed.")
    commit_id = commit.get("id")
    if commit_id is not None and not isinstance(commit_id, str):
        raise ReleaseGuardError("Render deploy response was malformed.")
    return commit_id


def preflight() -> None:
    api_key, _, service_id, commit_sha = required_configuration()
    window_start = (
        (datetime.now(UTC) - timedelta(minutes=5))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    recent_deploys = list_deploys(service_id, api_key, window_start)
    baseline_ids = sorted(
        deploy["id"]
        for deploy in recent_deploys
        if (deploy_commit_id(deploy) or "").lower() == commit_sha.lower()
    )

    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        raise ReleaseGuardError("GitHub Actions output file is unavailable.")
    try:
        with Path(output_file).open("a", encoding="utf-8") as output:
            output.write(
                "baseline_deploy_ids="
                + json.dumps(baseline_ids, separators=(",", ":"))
                + "\n"
            )
    except OSError:
        raise ReleaseGuardError("Could not save Render preflight results.") from None
    print("Render deployment configuration and API access validated.")


def build_hook_url(hook_url: str, commit_sha: str) -> str:
    parsed = urlsplit(hook_url)
    query = [(key, value) for key, value in parse_qsl(parsed.query) if key != "ref"]
    query.append(("ref", commit_sha))
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def trigger_deploy(hook_url: str, commit_sha: str) -> str | None:
    status_code, body = request_bytes(
        build_hook_url(hook_url, commit_sha),
        method="POST",
        label="Render deploy hook",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    return parse_hook_response(status_code, body)


def retrieve_deploy(service_id: str, deploy_id: str, api_key: str) -> dict[str, Any]:
    path = f"/services/{quote(service_id, safe='')}/deploys/{quote(deploy_id, safe='')}"
    payload = render_json(path, api_key=api_key, label="Render deploy response")
    if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
        raise ReleaseGuardError("Render deploy response was malformed.")
    return payload


def timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ReleaseGuardError("Render deploy timestamp was malformed.") from None
    if parsed.tzinfo is None:
        raise ReleaseGuardError("Render deploy timestamp was malformed.")
    return parsed


def find_queued_deploy(
    *,
    service_id: str,
    api_key: str,
    commit_sha: str,
    hook_started_at: datetime,
    baseline_ids: set[str],
    deadline: float,
) -> str:
    created_after = hook_started_at.isoformat(timespec="seconds").replace("+00:00", "Z")
    while time.monotonic() < deadline:
        for deploy in list_deploys(service_id, api_key, created_after):
            if deploy["id"] in baseline_ids or deploy.get("trigger") != "deploy_hook":
                continue
            if (deploy_commit_id(deploy) or "").lower() != commit_sha.lower():
                continue
            created_at = deploy.get("createdAt")
            if not isinstance(created_at, str):
                raise ReleaseGuardError("Queued Render deploy response was malformed.")
            deploy_id = deploy.get("id")
            if not isinstance(deploy_id, str) or not deploy_id:
                raise ReleaseGuardError("Queued Render deploy response was malformed.")
            if timestamp(created_at) >= hook_started_at:
                return deploy_id
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(DEPLOY_POLL_INTERVAL_SECONDS, remaining))
    raise ReleaseGuardError(
        "Queued Render deployment was not found before the timeout."
    )


def wait_for_live_deploy(
    *, service_id: str, deploy_id: str, api_key: str, commit_sha: str, deadline: float
) -> None:
    last_status = "unknown"
    while time.monotonic() < deadline:
        deploy = retrieve_deploy(service_id, deploy_id, api_key)
        returned_id = deploy.get("id")
        status = deploy.get("status")
        returned_sha = deploy_commit_id(deploy)
        if not isinstance(returned_id, str) or not isinstance(status, str):
            raise ReleaseGuardError("Render deploy response was malformed.")
        if returned_id != deploy_id or not returned_sha:
            raise ReleaseGuardError(
                "Render deploy response did not identify its commit."
            )
        if returned_sha.lower() != commit_sha.lower():
            raise ReleaseGuardError(
                "Render deployment commit did not match GITHUB_SHA."
            )
        last_status = status
        if status == "live":
            return
        if status in FAILED_STATUSES:
            raise ReleaseGuardError(
                f"Render deployment ended in terminal status '{status}'."
            )
        if status not in IN_PROGRESS_STATUSES:
            raise ReleaseGuardError("Render deployment returned an unknown status.")

        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(DEPLOY_POLL_INTERVAL_SECONDS, remaining))
    raise ReleaseGuardError(
        f"Render deployment did not reach live before the timeout (last status: {last_status})."
    )


def check_health_endpoint(path: str, timeout: float) -> None:
    status_code, body = request_bytes(
        f"{PUBLIC_API_ROOT}{path}",
        method="GET",
        label=f"Public {path}",
        headers={"Accept": "application/json"},
        timeout=timeout,
    )
    validate_health_response(path, status_code, body)


def wait_for_public_health() -> None:
    deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
    last_failure = "Public health checks did not pass."
    while time.monotonic() < deadline:
        try:
            for path, _ in HEALTH_ENDPOINTS:
                remaining = deadline - time.monotonic()
                check_health_endpoint(
                    path,
                    timeout=min(HEALTH_REQUEST_TIMEOUT_SECONDS, max(1, remaining)),
                )
            print("Public /health and /health/ready checks passed.")
            return
        except ReleaseGuardError as error:
            last_failure = str(error)

        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(HEALTH_POLL_INTERVAL_SECONDS, remaining))
    raise ReleaseGuardError(
        f"Public health verification timed out after {HEALTH_TIMEOUT_SECONDS} seconds; {last_failure}"
    )


def deploy() -> None:
    api_key, hook_url, service_id, commit_sha = required_configuration()
    baseline_raw = os.environ.get("RENDER_BASELINE_DEPLOY_IDS", "")
    try:
        baseline_ids_value = json.loads(baseline_raw)
    except json.JSONDecodeError:
        raise ReleaseGuardError("Render preflight state was malformed.") from None
    if not isinstance(baseline_ids_value, list) or any(
        not isinstance(value, str) for value in baseline_ids_value
    ):
        raise ReleaseGuardError("Render preflight state was malformed.")

    hook_started_at = datetime.now(UTC)
    deadline = time.monotonic() + DEPLOY_TIMEOUT_SECONDS
    deploy_id = trigger_deploy(hook_url, commit_sha)
    if deploy_id is None:
        deploy_id = find_queued_deploy(
            service_id=service_id,
            api_key=api_key,
            commit_sha=commit_sha,
            hook_started_at=hook_started_at,
            baseline_ids=set(baseline_ids_value),
            deadline=deadline,
        )

    wait_for_live_deploy(
        service_id=service_id,
        deploy_id=deploy_id,
        api_key=api_key,
        commit_sha=commit_sha,
        deadline=deadline,
    )
    print("Render deployment for GITHUB_SHA is live.")
    wait_for_public_health()


def validate() -> None:
    try:
        project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
        project_version = project["project"]["version"]
        from sentinel import __version__
    except ImportError, KeyError, OSError, tomllib.TOMLDecodeError, TypeError:
        raise ReleaseGuardError(
            "Could not read the project and package versions."
        ) from None
    if not isinstance(project_version, str) or not isinstance(__version__, str):
        raise ReleaseGuardError("Project and package versions must be strings.")
    validate_release_context(
        os.environ.get("GITHUB_EVENT_NAME", ""),
        os.environ.get("GITHUB_REF_TYPE", ""),
        os.environ.get("GITHUB_REF_NAME", ""),
        project_version,
        __version__,
    )
    print("Release tag and version checks passed.")


def main(arguments: list[str] | None = None) -> int:
    command_arguments = sys.argv[1:] if arguments is None else arguments
    if len(command_arguments) != 1 or command_arguments[0] not in {
        "validate",
        "validate-ancestry",
        "preflight",
        "deploy",
    }:
        print(
            "Usage: release_guard.py {validate|validate-ancestry|preflight|deploy}",
            file=sys.stderr,
        )
        return 2

    try:
        command = command_arguments[0]
        if command == "validate":
            validate()
        elif command == "validate-ancestry":
            validate_commit_reachable(os.environ.get("GITHUB_SHA", ""))
        elif command == "preflight":
            preflight()
        else:
            deploy()
    except ReleaseGuardError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
