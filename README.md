# Sentinel

Sentinel is a Python engineering-incident assistant that turns an incident
description into a structured investigation, runs controlled repository tools,
and records execution outcomes. An optional internal LangGraph path can propose
and apply a patch, verify it with tests, and retry when verification fails.

**Portfolio narrative:** Sentinel accepts an authenticated engineering
incident, investigates a known failure using repository tools, and records an
execution trace. In a separate deterministic fixture, it proposes a constrained
patch, checks it with the repository policy, runs tests, retries a failed
verification, and persists the outcome. The public API does not expose patch
application or human approval, and the deterministic fixture is not a claim of
general LLM accuracy.

## Architecture

- **FastAPI API:** incident creation, investigation initiation, health checks,
  and authenticated Prometheus metrics.
- **LangGraph workflow:** execution lifecycle, planner and investigator steps,
  and an optional internal repair/verification retry loop.
- **Agents:** an Ollama-backed planner creates investigation plans; the
  investigator maps plan steps to registered tools. The internal repair agent
  parses a proposed unified diff.
- **Tool gateway and policy:** controlled file/search/test tools and patch
  application. Repair paths must stay inside the configured repository; `.git`
  and selected `.env` files are protected, and patches must match file context.
- **Persistence:** repository ports have SQLite and PostgreSQL adapters for
  incidents, executions, tool audits, and repair history.
- **Operations:** request-ID middleware, structured JSON logs, standardized API
  errors, endpoint rate limits, and process-local HTTP metrics.

### Public API

The FastAPI application exposes an investigation API, not a patch API:

| Route | Capability |
| --- | --- |
| `POST /incidents` | Create an incident from a title and description. |
| `POST /incidents/{incident_id}/investigate` | Start an investigation and return incident/execution status. It does not return findings or apply a repair. |
| `GET /health` | Public shallow liveness-style response. |
| `GET /health/ready` | Check database connectivity. |
| `GET /health/ollama` | Authenticated, rate-limited provider health check. |
| `GET /metrics` | API-key-protected Prometheus text metrics; process-local and not aggregated across instances. |

The incident routes and Ollama health check require `X-API-Key` and are
rate-limited. Standardized errors include a request ID in the JSON body and
`X-Request-ID` response header.

### Internal Repair Workflow and Safety

The application factory defaults `enable_repair` to `false`, and the FastAPI
startup path does not enable it. When an internal caller explicitly enables
repair, the graph can create a repair plan, pass it through a
`RepairApprovalGate`, apply approved `apply_patch` steps, run the configured
test path, record attempts, and retry failed verification up to the retry
policy. If no gate is injected, the graph uses an **automatic approval gate**;
this is not human-in-the-loop approval. No reviewer UI or public approval route
is implemented.

The repair policy rejects absolute or repository-escaping paths, `.git`, and
`.env`, `.env.local`, and `.env.production` files. Unified-diff context must
match before a file is written. Sentinel does not create a Git branch, commit,
pull request, or deployment as part of repair.

## Technology

- Python 3.14, `uv`, FastAPI, Pydantic Settings, LangGraph, and the Ollama SDK
- MCP integration and a local tool gateway
- SQLite by default; optional PostgreSQL through Psycopg 3 and a bounded async
  connection pool
- Pytest, Ruff, and MyPy
- Prometheus-compatible metrics exposition; optional local Prometheus/Grafana
  files are documented separately

## Persistence and Deployment

Local development defaults to SQLite at `data/sentinel.db`. Set
`DATABASE_BACKEND=postgresql` with the separate `DB_*` settings to select the
PostgreSQL adapter. SQLite initializes its schema at startup; PostgreSQL uses
versioned schema migrations. Switching backends does not copy data. Keep
database passwords and API keys in local ignored configuration or a deployment
secret manager.

The release workflow is tag-triggered: for `v*` tags it runs formatting, lint,
type checks, and the non-integration test selection, then posts to the configured
Render deployment hook. It does not make the public API repair-capable. See
[`docs/postgresql.md`](docs/postgresql.md) for PostgreSQL/Render configuration
and persistence safety.

## Security and Observability

Protected endpoints use `SENTINEL_API_KEY` with constant-time comparison.
Request IDs correlate response headers and structured JSON logs; avoid putting
sensitive incident details in logs because request paths can contain IDs.
Unexpected API errors are sanitized. `/metrics` requires the API key, is not
public, and reports only process-local metrics; it resets on process restart and
is not automatically aggregated across instances. See
[`docs/api.md`](docs/api.md) for route semantics, metrics, PromQL examples, and
logging details. The optional local stack and secret handling are in
[`observability/local/README.md`](observability/local/README.md).

## Deterministic Evaluation

Run the existing fixed scenarios with:

```powershell
uv run python scripts/run_evaluation.py
```

The runner uses a deterministic mocked provider, a temporary calculator
repository, local tools, and isolated SQLite. It writes timestamped JSON and
Markdown reports under the ignored `data/evaluation-reports/` directory. The
suite covers six specified scenarios; its result is a fixture check, not a
performance benchmark or general model-accuracy score. Live Ollama planner
tests are separate and are not part of this runner. See
[`docs/evaluation.md`](docs/evaluation.md) for scenario criteria and report
semantics.

## Quick Start

Requirements: Python 3.14, `uv`, and a locally reachable Ollama model for the
API investigation path. Copy `.env.example` to `.env` (the latter is ignored),
set a local-only `SENTINEL_API_KEY`, and point `SENTINEL_REPOSITORY_ROOT` at an
authorized workspace. Do not use production credentials or repositories for a
portfolio rehearsal.

```powershell
uv sync --locked --dev
uv run uvicorn sentinel.api:app --host 127.0.0.1 --port 8000
```

The API will be available at `http://127.0.0.1:8000`. The deterministic
evaluation command above does not need the API server or Ollama.

## Further Reading

- [`docs/demo.md`](docs/demo.md): portfolio walkthrough and API-versus-internal
  workflow boundaries.
- [`docs/api.md`](docs/api.md): API error contracts, health endpoints, metrics,
  and request logging.
- [`docs/evaluation.md`](docs/evaluation.md): deterministic scenarios, results,
  and limitations.
- [`docs/postgresql.md`](docs/postgresql.md): PostgreSQL, Neon, Render, schema
  permissions, and safe database tests.
- [`observability/local/README.md`](observability/local/README.md): optional
  local Prometheus/Grafana stack setup.
- [`docs/ruff-lint-validation.md`](docs/ruff-lint-validation.md): validation
  history and repository checks.
