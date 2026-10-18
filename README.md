# Sentinel

## Autonomous Multi-Agent Engineering Ops Copilot

Sentinel is a production-oriented AI engineering system that autonomously
investigates software engineering incidents, plans fixes, uses controlled
tools to inspect and modify repositories, verifies changes through automated
testing, learns from previous incidents, and reports execution outcomes.

## Vision

Sentinel aims to demonstrate modern AI engineering patterns including:

- Multi-agent orchestration
- Planning and autonomous workflows
- Tool calling
- Model Context Protocol (MCP)
- Agent memory
- Automated verification
- Evaluation
- Observability
- Human-in-the-loop controls
- Production-oriented architecture

## Current Status

🚧 Project initialization — Sprint 0

## Technology

- Python
- LangGraph
- LangChain
- Ollama
- MCP
- FastAPI
- ChromaDB
- SQLite
- Pytest
- Docker

## Architecture

The project follows Clean Architecture principles with explicit separation
between domain logic, application services, infrastructure, agent
orchestration, and external interfaces.

## Development

### Install dependencies

```bash
uv sync
```

### Persistence

SQLite remains the local default. The API selects SQLite or PostgreSQL from
`DATABASE_BACKEND` and shares that backend across incident creation, investigations,
execution audits, and repair persistence. Domain models and application ports are
shared; the database adapters are separate. Autonomous repair remains disabled
by default in the API.

#### Local SQLite

Set this in your untracked `.env`, or leave `DATABASE_URL` unset if no `.env`
override exists:

```dotenv
DATABASE_URL=sqlite:///./data/sentinel.db
```

Sentinel creates the parent directory and initializes the SQLite schema at API
startup. Existing SQLite tests do not require a PostgreSQL server.

```bash
uv sync --locked --dev
uv run uvicorn sentinel.api:app --host 127.0.0.1 --port 8000
```

#### PostgreSQL Configuration

Set the PostgreSQL connection fields privately in `.env` for local development
or as separate environment variables on Render. `DATABASE_URL` continues to
select the local SQLite file; the PostgreSQL DSN is assembled from `DB_*` at
runtime. Never commit the password or a credential-bearing URL.

```dotenv
DATABASE_BACKEND=postgresql
DB_HOST=ep-example-pooler.region.aws.neon.tech
DB_PORT=5432
DB_NAME=<exact database name from Neon dashboard>
DB_USERNAME=<username from Neon dashboard>
DB_PASSWORD=<secret, never commit>
DB_SSLMODE=require
DATABASE_SCHEMA=sentinel
DATABASE_CONNECT_TIMEOUT_SECONDS=10
DATABASE_POOL_SIZE=5
```

`DB_NAME` is required and has no assumed default. Confirm its exact value in
Neon's dashboard: an existing Spring configuration uses `neondb`, while
`sentinel_db` was also suggested. Do not assume they identify the same database.
The password is a `SecretStr` and is percent-encoded when the DSN is built.
Remote connections require TLS; `DB_SSLMODE=require` is the production minimum.

PostgreSQL uses Psycopg 3 with a bounded async pool. Startup initializes a private,
versioned schema without dropping or copying data. Incidents, executions, tool
audits, repair attempts, steps, and verifications are supported. Schema setup
requires an appropriately privileged backend database role.

On Windows, use a selector loop when starting the PostgreSQL-backed API:

```powershell
uv run uvicorn sentinel.api:app --loop asyncio:SelectorEventLoop --host 127.0.0.1 --port 8000
```

#### Neon on Render

In Render's **Environment** settings, add these separate variables:

| Key | Value |
| --- | --- |
| `DATABASE_BACKEND` | `postgresql` |
| `DB_HOST` | `ep-lively-unit-a1pvq2yh-pooler.ap-southeast-1.aws.neon.tech` |
| `DB_PORT` | `5432` |
| `DB_NAME` | Exact database name verified in Neon dashboard (`neondb` or `sentinel_db`; confirm, do not guess) |
| `DB_USERNAME` | `neondb_owner` (verify against Neon connection details) |
| `DB_PASSWORD` | Actual Neon password; store only as a Render secret |
| `DB_SSLMODE` | `require` |

Leave `DATABASE_URL` at its SQLite default or omit it; it is not used when
`DATABASE_BACKEND=postgresql`. Keep `SENTINEL_API_KEY`, Ollama configuration,
and rate-limit behavior intact. `/health` remains public. Validate against a
dedicated non-production Neon database before deployment; SQLite data is never
copied automatically.

See [the PostgreSQL setup guide](docs/postgresql.md) for schema permissions,
pool sizing, migration safety, and TLS details.

### Monitoring

`/health` is a public liveness-style check; `/health/ready` checks database
access, and `/health/ollama` checks the provider with API-key authentication.
`/metrics` is a separate, API-key-protected Prometheus endpoint. Metrics are
process-local, reset on restart, and are not automatically aggregated across
instances. See [the API monitoring guide](docs/api.md) for metric queries,
external-scraper guidance, and logging details.

#### Safe PostgreSQL Integration Tests

Configure `TEST_POSTGRES_URL` privately for a dedicated test database, never the
production Neon database or the configured application database. Tests create
and clean up randomized test schemas; the test role needs schema creation rights.
Without this variable, PostgreSQL integration tests skip without network calls.

```bash
uv run pytest -q tests/integration/persistence/test_postgres.py
```

For localhost testing using your private `.env` credentials, the isolated runner
automatically creates and removes a temporary test database, leaving the
application database untouched:

```powershell
uv run python -m tests.fixtures.postgres
```

This command refuses remote endpoints and requires local CREATE DATABASE
permission. It selects the appropriate Windows event loop automatically.

On Windows, run these tests with a selector event loop:

```powershell
uv run python -c "import asyncio, pytest; asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()); raise SystemExit(pytest.main(['-q', 'tests/integration/persistence/test_postgres.py']))"
```

The standard validation commands are:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

For the deterministic autonomous-repair evaluation scenarios, coverage map,
pass criteria, and measurement guidance, see [the evaluation baseline](docs/evaluation.md).

The full suite also includes existing live Ollama tests; those require the
configured provider. The existing CI selection is `uv run pytest -q -m 'not integration'`.
