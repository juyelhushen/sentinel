# Sentinel Portfolio Demo

This walkthrough uses two distinct paths. The deterministic local evaluation
demonstrates the internal repair workflow on an isolated fixture. The FastAPI
path demonstrates authenticated incident intake and investigation status; it
does not expose repair execution. No production endpoint is called by this
guide.

## Architecture at a Glance

- **FastAPI (`sentinel.api`)** validates and stores incident requests, protects
  operational endpoints with `X-API-Key`, and returns execution status from
  investigation requests.
- **Application/bootstrap layer** assembles the configured LLM provider,
  investigation service, LangGraph workflow, tool gateway, and persistence
  adapters.
- **Planner and investigator agents** produce a structured investigation plan
  and execute its allowed read/search/test tools against the configured
  repository root.
- **Internal repair workflow** can plan a unified diff, pass it through an
  approval gate, apply it with `ApplyPatchTool`, run verification tests, and
  retry failures up to the configured limit. The API factory does not enable
  this workflow.
- **Persistence adapters** use SQLite locally by default or PostgreSQL when
  configured. Incidents, executions, tool audits, and repair attempts have
  separate repositories.
- **Request middleware** assigns or validates `X-Request-ID`, emits structured
  request logs, and records process-local HTTP metrics. Standardized API errors
  include a request ID in the response envelope and header.

## Prerequisites and Local Configuration

The project requires Python 3.14 and `uv`. The public local API uses the
configured Ollama provider, so Ollama must be installed and reachable with a
model available locally. The deterministic evaluation runner does not require
Ollama.

Create an untracked `.env` at the repository root with local-only values:

```dotenv
DATABASE_BACKEND=sqlite
DATABASE_URL=sqlite:///./data/sentinel.db
SENTINEL_REPOSITORY_ROOT=./workspace
SENTINEL_API_KEY=<LOCAL_ONLY_API_KEY>
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=<LOCALLY_AVAILABLE_MODEL>
```

Replace placeholders locally; do not commit the file or paste credentials into
the demo recording. `.env` is gitignored. The API uses `SENTINEL_REPOSITORY_ROOT`
for investigation tools; the incident-create request does not accept a
repository path.

Install and start the API bound to loopback:

```powershell
uv sync --locked --dev
uv run uvicorn sentinel.api:app --host 127.0.0.1 --port 8000
```

The API lifespan initializes the selected persistence backend before serving
requests. For SQLite this creates the configured local database. PostgreSQL
requires the separate settings and permissions documented in
[`postgresql.md`](postgresql.md); this demo does not connect to Neon or change
Render settings.

## Deterministic Evaluation

Run the repeatable internal repair suite from the repository root:

```powershell
uv run python scripts/run_evaluation.py
```

The runner executes six existing pytest scenarios using a fixed provider,
temporary calculator repository, real local tool execution, and isolated
SQLite. It needs no live model service and never calls the public or deployed
API. It writes timestamped JSON and Markdown reports under
`data/evaluation-reports/`, which is gitignored. The report includes outcome,
retry count where available, duration, and safe error category; it excludes raw
incident text and patch contents. The calculator fact check is one small
deterministic fixture, not a general model-accuracy benchmark. See
[`evaluation.md`](evaluation.md) for scenario definitions and report semantics.

For a focused safe-rejection demonstration:

```powershell
uv run pytest -q tests/integration/workflows/test_autonomous_repair.py::test_invalid_repair_proposal_fails_through_investigation_service
```

This internal test feeds a structurally invalid repair step containing an
otherwise valid patch through `InvestigationService`. It verifies the parser
error is observable, the execution and incident are persisted as failed, no
patch tool is invoked, and the temporary source file remains unchanged. There
is no public API endpoint for submitting repair proposals.

## Local API Walkthrough

Use only the loopback server started above. These PowerShell examples are
illustrative and should be run against `http://127.0.0.1:8000`, never against a
production URL during a portfolio rehearsal. Substitute a locally managed key
for the placeholder without committing it:

```powershell
$baseUrl = "http://127.0.0.1:8000"
$headers = @{ "X-API-Key" = "<LOCAL_ONLY_API_KEY>" }
$body = @{
    title = "Calculator addition test fails"
    description = "The add function returns subtraction results."
} | ConvertTo-Json

$created = Invoke-WebRequest -Method Post `
    -Uri "$baseUrl/incidents" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body

$created.Headers["X-Request-ID"]
$created.Content | ConvertFrom-Json
```

`POST /incidents` accepts only `title` (3-200 characters) and `description`
(5-5000 characters). An illustrative success body, with generated values
redacted, is:

```json
{
  "id": "<INCIDENT_UUID>",
  "title": "Calculator addition test fails",
  "description": "The add function returns subtraction results.",
  "repository": "<CONFIGURED_REPOSITORY_ROOT>",
  "status": "created",
  "created_at": "<UTC_TIMESTAMP>"
}
```

Trigger its investigation:

```powershell
$incident = $created.Content | ConvertFrom-Json
$investigation = Invoke-WebRequest -Method Post `
    -Uri "$baseUrl/incidents/$($incident.id)/investigate" `
    -Headers $headers

$investigation.Headers["X-Request-ID"]
$investigation.Content | ConvertFrom-Json
```

The endpoint accepts no body. An illustrative successful response shape is:

```json
{
  "incident_id": "<INCIDENT_UUID>",
  "incident_status": "verifying",
  "execution_id": "<EXECUTION_UUID>",
  "execution_status": "completed",
  "error": null
}
```

These values are examples based on the response construction and local API
tests. The response does not include the investigation plan or tool findings.
In the API factory, repair is disabled, so this request does not create a repair
plan, apply a patch, invoke approval, or run repair verification. It can execute
investigation tools against the configured repository and returns status only.

An unauthenticated protected request returns HTTP 401 with the standardized
error envelope. The request ID is also returned in the `X-Request-ID` header:

```json
{
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Authentication failed.",
    "request_id": "<REQUEST_UUID>"
  }
}
```

Rate-limited routes return HTTP 429 and preserve a `Retry-After` header.

## Deployed Render API Path

The deployed API exposes the same FastAPI routes after the release workflow
triggers a Render deployment from a `v*` tag. Use the service's configured
HTTPS origin in a separately authorized environment; do not put the origin's
API key in this guide. Protected endpoints include `POST /incidents`,
`POST /incidents/{incident_id}/investigate`, `GET /health/ollama`, and
`GET /metrics`. They require `X-API-Key`. Incident creation, investigation,
and Ollama health are rate limited; `/metrics` is authenticated but is not
rate limited. The deployed API uses PostgreSQL when configured for that backend.

Health scopes are distinct: `/health` is public and shallow; `/health/ready`
checks database connectivity; `/health/ollama` requires authentication and
checks the provider. `/metrics` is authenticated and process-local. None of
these endpoints accepts or performs a patch operation. This documentation does
not invoke Render, modify deployment settings, or create production incidents.

## Inspecting the Run

- **Request ID:** read `X-Request-ID` from each response. Valid incoming UUIDs
  are preserved; otherwise middleware generates one.
- **Logs:** the local Uvicorn process writes structured JSON to its console.
  Request records include request ID, method, path, status, and duration. Paths
  may contain incident IDs, so protect log access and avoid recording sensitive
  descriptions in the example incident.
- **API errors:** standardized error responses use an `error` object containing
  `code`, `message`, and `request_id`; the same ID is in `X-Request-ID`. A 429
  also preserves `Retry-After`.
- **Evaluation outcomes:** review the JSON/Markdown report for actual outcome,
  pass/fail, execution count, elapsed time, retries, and safe error category.
  The report intentionally omits raw findings, test output, prompts, and patches.
- **Persistence:** the manually run local API stores incidents and executions
  in `data/sentinel.db` by default; tool audit rows are also persisted. A local
  SQLite viewer can inspect status/timestamps with queries such as:

  ```sql
  SELECT id, status, created_at, updated_at
  FROM incidents
  ORDER BY created_at DESC;

  SELECT id, incident_id, status, started_at, completed_at
  FROM executions
  ORDER BY started_at DESC;

  SELECT tool_name, status, started_at, completed_at
  FROM tool_executions
  ORDER BY started_at DESC;
  ```

  Avoid selecting incident descriptions, tool arguments, output, or errors when
  presenting logs or records. The deterministic evaluation scenarios use
  isolated pytest temporary databases; their repair attempts and verification
  records are asserted in
  [`test_autonomous_repair.py`](../tests/integration/workflows/test_autonomous_repair.py)
  and are not exported in the report. PostgreSQL records require a separately
  authorized, non-production database inspection.

## Internal Repair Boundaries

The deterministic test workflow explicitly enables repair in
`create_sentinel_application`. It plans a patch, invokes the configured
`RepairApprovalGate`, records each attempt, applies approved patch steps, runs
the configured test path, and retries failed verification up to the retry
policy. When no gate is injected, the graph uses an automatic approval gate.
This is not human-in-the-loop approval. A custom gate can be injected by
internal callers, but the public API does not expose such a control.

The repair parser accepts `apply_patch` steps. `RepairPolicy` restricts paths
to the configured repository root and rejects `.git` and selected `.env`
files; the unified-diff applier validates patch context. These controls do not
make arbitrary repositories safe to modify: only run the internal repair demo
on a disposable fixture or an explicitly authorized workspace. Sentinel does
not create a Git branch, commit, pull request, or deployment as part of this
workflow.

## Limitations and Next Steps

- The public API exposes incident creation and investigation status, not repair
  proposals, patch application, approval decisions, or verification details.
- Default internal approval is automatic; there is no reviewer UI or public
  approval endpoint.
- Repair verification runs local pytest through the tool gateway. It is not a
  sandboxed hosted build service.
- Local SQLite and process-local metrics are for development/demo use; Render
  PostgreSQL is configured separately. Do not point the demo at production.
- The deterministic suite checks fixed scenarios, not general Ollama quality.
  Live-model evaluation is separate and is not performed by this walkthrough.
- A future portfolio extension could provide a deliberate review interface,
  stronger workspace isolation, and richer sanitized result retrieval before
  making repair decisions available through an API.