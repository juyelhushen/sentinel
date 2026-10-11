# PostgreSQL Persistence on Neon and Render

## Design

Sentinel supports SQLite and PostgreSQL without changing its domain models or application repository ports. `DATABASE_BACKEND` selects the adapter. `sentinel.bootstrap.persistence` constructs one bundle of incident, execution, audit, and repair repositories and owns its lifecycle through `open_persistence`.

FastAPI lifespan shares that bundle with incident creation and investigation. The investigation factory delegates tool/agent/graph construction to the canonical application factory and remains compatible with its legacy SQLite `database_path` argument. The application factory accepts either database adapter or an already initialized persistence bundle. The CLI entry point also uses the same managed, configuration-selected persistence instead of forcing the legacy SQLite helper. API startup does not enable autonomous repair. Authentication, constant-time API-key comparison, endpoint rate limits, health endpoints, and Ollama settings remain unchanged.

PostgreSQL uses psycopg 3 and a bounded asynchronous connection pool per application process. Each repository operation borrows a connection for one transaction; a repair attempt and its steps/verifications are written atomically on the same connection. Incident, execution, and audit writes also accept an injected PostgreSQL connection without committing, rolling back, or closing it. The caller must acquire it through `PostgreSQLDatabase.connection()` so the schema is selected for that transaction.

The pool is opened at startup and closed at shutdown, including failed schema initialization. A shared PostgreSQL transaction scope consistently preserves injected connection ownership across repository writes. Database SQL and connection waits are asynchronous. SQLite adapter-owned operations use the managed transaction context, which commits or rolls back and always closes the connection; injected connections remain caller-owned. SQLite schema initialization is offloaded from the API event loop. SQLite repository SQL remains synchronous, as before.

## Environment Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_BACKEND` | `sqlite` | Select `sqlite` or `postgresql`. |
| `DATABASE_URL` | `sqlite:///./data/sentinel.db` | SQLite URL, used only for the SQLite backend. |
| `DB_HOST` | None | Required for PostgreSQL; host supplied by Neon. |
| `DB_PORT` | `5432` | PostgreSQL port. |
| `DB_NAME` | None | Required for PostgreSQL. Exact Neon database name; no default is assumed. |
| `DB_USERNAME` | None | Required for PostgreSQL; role supplied by Neon. |
| `DB_PASSWORD` | None | Required for PostgreSQL; stored as a `SecretStr`. |
| `DB_SSLMODE` | `require` | TLS mode: `require`, `verify-ca`, or `verify-full`. |
| `DATABASE_SCHEMA` | `sentinel` | Private PostgreSQL schema for Sentinel tables. Simple SQL identifier, at most 63 characters. |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | `10` | Connection/pool-acquisition timeout; 1-300 seconds. A URL's explicit `connect_timeout` is preserved for the driver connection. |
| `DATABASE_POOL_SIZE` | `5` | Maximum pooled connections per process; 1-50. Multiply by workers/instances when sizing Neon capacity. |
| `SENTINEL_API_KEY` | None | Existing required authentication for protected endpoints. Keep it secret. |
| `SENTINEL_REPOSITORY_ROOT` | `./workspace` | Existing investigation workspace. |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Existing defaults | Existing provider configuration. |
| `LLM_TIMEOUT_SECONDS` | `60` | Existing LLM timeout, unchanged by this migration. |

For local SQLite development, `DATABASE_BACKEND=sqlite` and `DATABASE_URL` retain their defaults. PostgreSQL settings are validated only when `DATABASE_BACKEND=postgresql`; a missing-field error lists variable names only. Configure Neon fields separately in Render, along with optional pool/schema/timeout variables. Keep existing API-key, Ollama, workspace, and start-command settings.

Do not put the password in source, test files, documentation, GitHub, shell command history, or chat. Use Render's secret environment setting for `DB_PASSWORD` and a local untracked secret environment file or secret manager. Settings repr and application error responses do not include the password or driver details. The constructed DSN is used only internally to open psycopg connections.

## Neon Connection Settings

Use the Neon host, username, database name, and pooler endpoint shown by your project. Sentinel constructs a psycopg DSN from separate `DB_*` variables and percent-encodes credentials internally. It never logs the constructed DSN.

Use the provided pooled host `ep-lively-unit-a1pvq2yh-pooler.ap-southeast-1.aws.neon.tech` and port `5432`; verify username `neondb_owner` in Neon connection details. The request gives conflicting database names: `sentinel_db` and the Spring configuration's `neondb`. This repository cannot verify whether they refer to the same database. `DB_NAME` is required with no assumed default; copy the exact name from the Neon dashboard.

For remote connections, `DB_SSLMODE=require` is the minimum. Stronger `verify-ca` and `verify-full` modes are supported when the corresponding CA is configured. `disable`, `allow`, and `prefer` are rejected for remote hosts. Only explicitly local loopback connections may use `disable` for development.

The Neon database name cannot be discovered safely from this repository. Confirm it in the Neon dashboard and configure `DB_NAME` accordingly before deployment.

## Schema Initialization and Permissions

The application creates a dedicated `sentinel` schema by default, then records migration version 1 in that schema's `schema_migrations` table. A transaction-scoped advisory lock serializes concurrent startups. Schema creation, tables, indexes, and the version record commit atomically. Subsequent startups skip applied migrations. A newer unsupported migration version fails closed.

Tables cover all existing persistence contracts:

- `incidents`: UUID identifiers, status, metadata, and timezone-aware timestamps.
- `executions`: UUID identifiers and cascading foreign key to incidents.
- `tool_executions`: request UUID, optional execution UUID, JSONB arguments, text output/errors, and timestamps.
- `repair_attempts`: cascading execution foreign key, unique `(execution_id, attempt_number)`, plan UUID/summary, approval metadata, and execution error.
- `repair_steps`: cascading attempt foreign key and patch data.
- `verifications`: cascading attempt foreign key and verification outcomes.

All SQLite relationship constraints and lookup indexes are preserved. The audit execution ID deliberately has no foreign key, matching SQLite: current investigator requests can have no execution ID, and existing audit records may use an unlinked UUID. This migration does not change that application-level correlation behavior.

Use a dedicated backend database role, not a browser/API key. At initial startup it needs permission to create the configured schema/tables/indexes, or ownership of a pre-provisioned empty schema. For a pre-provisioned schema, grant only the needed role access and ownership/CREATE rights. Subsequent operations need schema USAGE and table SELECT/INSERT/UPDATE/DELETE (repair updates replace child rows). This version initializes migrations during startup, so the configured role must continue to have the necessary DDL rights. Separate migration/runtime roles are not implemented here.

Keep the Sentinel schema private and do not grant untrusted client roles access to it. Sentinel uses a server-side SQL role; its API-key authentication is not a substitute for database-role isolation.

Initialization does not drop tables, truncate data, or copy SQLite data. If pre-existing conflicting tables exist in the configured schema without the migration record, initialization fails rather than silently adopting or altering them. Choose a clean private schema or review an explicit migration. Future schema changes should be added as new numbered, atomic migrations; do not alter an already-applied migration definition.

## Safe Tests

Unit tests and existing SQLite tests need no live Neon connection. New PostgreSQL integration tests do nothing unless `TEST_POSTGRES_URL` is configured. Never use the production Neon URL for this variable. Use a separate local test database or a dedicated non-production Neon database and test role.

Each integration test creates a randomized `sentinel_test_<uuid>` schema, initializes the schema there, and drops only that test schema during cleanup. Before connecting, the guard resolves the selected application backend DSN from the same Settings object used by the application, including `.env`. Matching host/database targets are rejected even if ports differ, and loopback aliases are treated as equivalent. Test URLs must explicitly identify a host and database. These conservative checks are a guard, not proof that differently named pooled/direct endpoints belong to different projects. You are responsible for supplying a genuinely non-production test endpoint. The test role needs CREATE schema and rights to delete its own isolated schema. No production data is copied or touched.

Set the test URL privately through a secret environment file/manager, not a literal command containing credentials. Then run:

```powershell
uv run pytest -q tests/integration/persistence/test_postgres.py
```

For repeatable local testing, configure `DATABASE_BACKEND=postgresql` and the local `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USERNAME`, and `DB_PASSWORD` privately in `.env`, then run:

```powershell
uv run python -m tests.fixtures.postgres
```

This runner refuses remote endpoints, creates a randomized temporary database on the local server, supplies its URL only for the test process, and removes that database after tests finish, including test failures. It never runs destructive tests inside the application database. The local role needs CREATE DATABASE permission. The runner also restores pre-existing process environment settings. Creation/cleanup failures are reported without connection details. On Windows it selects the psycopg-compatible event loop automatically; Python 3.14 currently emits deprecation warnings for the policy API used by pytest. These warnings do not indicate test failures.

On Windows, psycopg async connections require a selector loop. For live PostgreSQL tests, use this Python 3.14 invocation after configuring the dedicated test URL privately:

```powershell
uv run python -c "import asyncio, pytest; asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()); raise SystemExit(pytest.main(['-q', 'tests/integration/persistence/test_postgres.py']))"
```

The same selector-loop requirement applies if you run the PostgreSQL-backed API locally on Windows; SQLite local development needs no loop change. Render's Linux environment does not have this Windows-specific requirement.

Exact requested validation commands:

```powershell
uv sync --locked --dev
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

Focused network-free migration/security checks:

```powershell
uv run pytest -q tests/unit/infrastructure/database/test_postgres.py tests/unit/infrastructure/database/test_postgres_schema.py tests/unit/infrastructure/persistence/test_postgres_repositories.py tests/unit/bootstrap/test_persistence.py tests/unit/test_api.py
```

The existing full suite includes live Ollama integration tests; an Ollama timeout is distinct from a database migration failure. The existing CI selection remains `uv run pytest -q -m 'not integration'`; no old tests or markers were changed.

## Scope and Limitations

All four existing repository contracts are implemented for PostgreSQL, including repair attempts, steps, and verifications. Autonomous repair is still disabled in the API. No SQLite-to-PostgreSQL data-transfer tool, multi-operation unit of work for an entire investigation, or separate offline migration CLI is added. An investigation persists through the existing sequence of repository operations; individual operations and repair writes are atomic.

`/health` remains public and does not query the database. Startup requires successful database schema initialization; a failed startup prevents serving any routes until configuration/connectivity is corrected. Runtime PostgreSQL failures return a generic HTTP 503. Endpoint rate limiting remains per-process/in-memory and is not distributed across Render instances, matching existing behavior.

No Neon resources are provisioned and no deployment, commit, or push is performed by this change. The supplied Neon database name was not independently verified; confirm it in the Neon dashboard and verify connectivity against a dedicated non-production database before deploying production.

## Change Inventory

Added:

- [src/sentinel/bootstrap/persistence.py](../src/sentinel/bootstrap/persistence.py): shared URL-based adapter/repository selection and managed startup/shutdown.
- [src/sentinel/infrastructure/database/postgres.py](../src/sentinel/infrastructure/database/postgres.py): async psycopg pool, TLS/configuration validation, connection transactions, and sanitized failures.
- [src/sentinel/infrastructure/database/postgres_schema.py](../src/sentinel/infrastructure/database/postgres_schema.py): atomic version-1 schema migration and concurrent-startup lock.
- [src/sentinel/infrastructure/persistence/postgres/incident_repository.py](../src/sentinel/infrastructure/persistence/postgres/incident_repository.py): incident repository port implementation.
- [src/sentinel/infrastructure/persistence/postgres/execution_repository.py](../src/sentinel/infrastructure/persistence/postgres/execution_repository.py): execution repository port and SQLite-compatible nullable timestamp ordering.
- [src/sentinel/infrastructure/persistence/postgres/tool_execution_repository.py](../src/sentinel/infrastructure/persistence/postgres/tool_execution_repository.py): audit persistence with JSONB arguments.
- [src/sentinel/infrastructure/persistence/postgres/repair_repository.py](../src/sentinel/infrastructure/persistence/postgres/repair_repository.py): atomic repair attempts, steps, and verifications.
- [tests/unit/infrastructure/database/test_postgres.py](../tests/unit/infrastructure/database/test_postgres.py): network-free TLS, configuration, pool lifecycle, and failure tests.
- [tests/unit/infrastructure/database/test_postgres_schema.py](../tests/unit/infrastructure/database/test_postgres_schema.py): migration-version and non-destructive initialization tests.
- [tests/unit/infrastructure/persistence/test_postgres_repositories.py](../tests/unit/infrastructure/persistence/test_postgres_repositories.py): binding, row mapping, connection ownership, and timestamp ordering tests.
- [tests/unit/bootstrap/test_persistence.py](../tests/unit/bootstrap/test_persistence.py): both backend selections and cleanup on initialization failure.
- [tests/unit/test_api.py](../tests/unit/test_api.py): authentication, endpoint rate-limit isolation, lifecycle, endpoint behavior, and error sanitization.
- [tests/integration/persistence/test_postgres.py](../tests/integration/persistence/test_postgres.py): opt-in isolated PostgreSQL CRUD, audit, foreign-key, rollback, concurrent migration, and repair contract tests.
- [docs/postgresql.md](postgresql.md): this configuration, safety, testing, and validation guide.

Modified:

- [pyproject.toml](../pyproject.toml) and [uv.lock](../uv.lock): add psycopg binary and async-pool dependencies through uv.
- [src/sentinel/config/settings.py](../src/sentinel/config/settings.py): add `DATABASE_BACKEND`, typed `DB_*` settings, selected-backend URL construction with percent-encoded credentials, and conditional validation that names missing fields without echoing the password.
- [src/sentinel/bootstrap/investigation.py](../src/sentinel/bootstrap/investigation.py): inject shared persistence while retaining legacy SQLite-path compatibility.
- [src/sentinel/bootstrap/application.py](../src/sentinel/bootstrap/application.py): accept both adapters or the shared bundle without enabling repair by default.
- [src/sentinel/api.py](../src/sentinel/api.py): own shared persistence lifecycle and return sanitized database failures. Security dependency implementations are unchanged.
- [src/sentinel/main.py](../src/sentinel/main.py): use the same selected persistence bundle in the CLI and a PostgreSQL-compatible selector loop, preserving its existing incident-creation output.
- [tests/unit/test_main.py](../tests/unit/test_main.py): isolate CLI persistence on temporary SQLite storage and verify PostgreSQL factory/lifecycle wiring without network access.
- [tests/unit/config/test_settings.py](../tests/unit/config/test_settings.py): verify database environment values and secret-safe Settings representation.
- [.env.example](../.env.example): preserve SQLite defaults and provide commented Neon environment names without a password or guessed database name.
- [README.md](../README.md): link this guide.

## Persistence Refactoring Follow-Up

- [src/sentinel/infrastructure/database/sqlite.py](../src/sentinel/infrastructure/database/sqlite.py): delegate commit/rollback to the connection context and always close owned connections, including failure paths.
- [src/sentinel/infrastructure/database/schema.py](../src/sentinel/infrastructure/database/schema.py): close the schema initializer's owned SQLite connection through the managed transaction context.
- SQLite incident, execution, tool-audit, and repair adapters under `src/sentinel/infrastructure/persistence/sqllite`: consistently manage owned connections, remove redundant commits/dynamic imports, and separate incident row mapping from retrieval. The connection-injected legacy incident adapter retains caller ownership.
- PostgreSQL incident, execution, tool-audit, and repair adapters: use shared PostgreSQL transaction ownership and consistent query/row mapping separation, without changing SQL fields or application contracts.
- [src/sentinel/bootstrap/application.py](../src/sentinel/bootstrap/application.py) and [src/sentinel/bootstrap/investigation.py](../src/sentinel/bootstrap/investigation.py): one canonical agent/tool/graph construction path, with a concrete compiled-graph return annotation and legacy SQLite path compatibility.
- [tests/fixtures/postgres.py](../tests/fixtures/postgres.py): shared test-target safeguards and repeatable isolated local test runner; unit tests no longer import an integration-test module.
- [tests/unit/infrastructure/database/test_sqlite.py](../tests/unit/infrastructure/database/test_sqlite.py): owned connection closure on success and failure.
- [tests/unit/bootstrap/test_persistence.py](../tests/unit/bootstrap/test_persistence.py): remote refusal, temporary-database cleanup, environment restoration, and existing production-target safeguards.
- [tests/integration/persistence/test_postgres.py](../tests/integration/persistence/test_postgres.py): real PostgreSQL investigation factory coverage with a fake LLM, in addition to all persistence contract tests.

No credential values were added to tracked files. Domain models, application ports, API authentication/rate-limit implementations, and repair-safety policies remain unchanged.

## Local Validation Results

- `uv run ruff format --check .`: PASS, 252 files formatted.
- `uv run ruff check .`: PASS.
- `uv run mypy src`: PASS, 132 source files.
- `uv run pytest`: PASS, 264 passed and 6 skipped.
- `uv run pytest -q -m 'not integration'`: PASS, 256 passed, 1 skipped, 13 deselected.
- `uv run python -m tests.fixtures.postgres`: PASS, 5 real PostgreSQL tests passed and the temporary local test database was removed.
- `uv lock --check`: PASS, 82 packages resolved.

The standard full suite leaves live PostgreSQL integrations opt-in unless `TEST_POSTGRES_URL` is configured. They were also executed separately using the local-only runner: native UUID/JSONB/timestamp mapping, foreign keys, rollback, duplicate writes, concurrent migrations, atomic repair writes, and the investigation factory all passed against actual local PostgreSQL. The production Neon/Render endpoint remains unverified; local PostgreSQL testing is not a substitute for testing against a dedicated non-production Neon database.

The actual Neon database name remains unverified. Confirm whether it is `neondb`, `sentinel_db`, or another name in Neon, then set `DB_NAME` in Render. No credential is required in the repository or conversation.