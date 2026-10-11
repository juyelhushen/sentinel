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
`DATABASE_URL` and shares that backend across incident creation, investigations,
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

Set the PostgreSQL connection URL privately in `.env` for local development or
in the service environment on Render. Never commit the real username/password
or complete connection URL. Supported URL schemes are `postgresql://` and
`postgres://`; other database schemes are rejected.

```dotenv
DATABASE_URL=postgresql://USERNAME:PASSWORD@HOST:PORT/DATABASE?sslmode=require
DATABASE_SCHEMA=sentinel
DATABASE_CONNECT_TIMEOUT_SECONDS=10
DATABASE_POOL_SIZE=5
```

The URL above contains placeholders, not working credentials. Percent-encode
reserved characters in passwords. Remote connections require TLS; supplied
`verify-full` and certificate parameters are preserved. Only local loopback
connections may explicitly use `sslmode=disable`.

PostgreSQL uses Psycopg 3 with a bounded async pool. Startup initializes a private,
versioned schema without dropping or copying data. Incidents, executions, tool
audits, repair attempts, steps, and verifications are supported. Schema setup
requires an appropriately privileged backend database role.

On Windows, use a selector loop when starting the PostgreSQL-backed API:

```powershell
uv run uvicorn sentinel.api:app --loop asyncio:SelectorEventLoop --host 127.0.0.1 --port 8000
```

#### Supabase on Render

1. In Supabase's **Connect** dialog, copy the connection URL for the appropriate
	connection mode. Keep its supplied host, port, database, and username.
2. For a persistent Render backend without working IPv6 connectivity, prefer the
	shared **session pooler**. Use the direct endpoint only if it is reachable.
	Transaction-pooler connections are also supported: prepared statements are
	disabled and schema selection is transaction-local.
3. Put the real `DATABASE_URL` in Render's secret environment settings, with
	`sslmode=require` or stronger certificate verification. Do not use the local
	TLS opt-out remotely.
4. Keep `SENTINEL_API_KEY`, Ollama configuration, and existing rate limits intact.
	Protected endpoints require the configured key; `/health` remains public.
5. Deploy only after reviewing the changes and testing against a dedicated
	non-production PostgreSQL database. No SQLite data is copied automatically.

See [the PostgreSQL setup guide](docs/postgresql.md) for schema permissions,
pool sizing, migration safety, and TLS details.

#### Safe PostgreSQL Integration Tests

Configure `TEST_POSTGRES_URL` privately for a dedicated test database, never the
production Supabase database or the configured application database. Tests create
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

The full suite also includes existing live Ollama tests; those require the
configured provider. The existing CI selection is `uv run pytest -q -m 'not integration'`.
