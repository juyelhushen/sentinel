# PostgreSQL Persistence on Supabase and Render

## Design

Sentinel supports SQLite and PostgreSQL without changing its domain models or application repository ports. `sentinel.bootstrap.persistence` selects the database from `DATABASE_URL`, constructs one bundle of incident, execution, audit, and repair repositories, and owns its lifecycle through `open_persistence`.

FastAPI lifespan shares that bundle with incident creation and investigation. The investigation factory delegates tool/agent/graph construction to the canonical application factory and remains compatible with its legacy SQLite `database_path` argument. The application factory accepts either database adapter or an already initialized persistence bundle. The CLI entry point also uses the same managed, configuration-selected persistence instead of forcing the legacy SQLite helper. API startup does not enable autonomous repair. Authentication, constant-time API-key comparison, endpoint rate limits, health endpoints, and Ollama settings remain unchanged.

PostgreSQL uses psycopg 3 and a bounded asynchronous connection pool per application process. Each repository operation borrows a connection for one transaction; a repair attempt and its steps/verifications are written atomically on the same connection. Incident, execution, and audit writes also accept an injected PostgreSQL connection without committing, rolling back, or closing it. The caller must acquire it through `PostgreSQLDatabase.connection()` so the schema is selected for that transaction.

The pool is opened at startup and closed at shutdown, including failed schema initialization. A shared PostgreSQL transaction scope consistently preserves injected connection ownership across repository writes. Database SQL and connection waits are asynchronous. SQLite adapter-owned operations use the managed transaction context, which commits or rolls back and always closes the connection; injected connections remain caller-owned. SQLite schema initialization is offloaded from the API event loop. SQLite repository SQL remains synchronous, as before.

## Environment Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./data/sentinel.db` | SQLite URL or Supabase PostgreSQL secret URL. Both `postgres://` and `postgresql://` are accepted. |
| `DATABASE_SCHEMA` | `sentinel` | Private PostgreSQL schema for Sentinel tables. Simple SQL identifier, at most 63 characters. |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | `10` | Connection/pool-acquisition timeout; 1-300 seconds. A URL's explicit `connect_timeout` is preserved for the driver connection. |
| `DATABASE_POOL_SIZE` | `5` | Maximum pooled connections per process; 1-50. Multiply by workers/instances when sizing Supabase capacity. |
| `SENTINEL_API_KEY` | None | Existing required authentication for protected endpoints. Keep it secret. |
| `SENTINEL_REPOSITORY_ROOT` | `./workspace` | Existing investigation workspace. |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Existing defaults | Existing provider configuration. |
| `LLM_TIMEOUT_SECONDS` | `60` | Existing LLM timeout, unchanged by this migration. |

For local SQLite development, no database environment changes are necessary. Render must have `DATABASE_URL` set to the secret PostgreSQL URL. Set optional pool/schema/timeout variables in Render's environment settings. Keep existing API-key, Ollama, workspace, and start-command settings.

Do not put the real URL or password in source, test files, documentation, GitHub, shell command history, or chat. Use Render's secret environment settings and a local untracked secret environment file or your secret manager. The Settings representation excludes `DATABASE_URL`; application error responses never include driver messages or connection strings.

## Supabase Connection Choice

Use the URL supplied by your project's **Connect** dialog. Host, port, database, and username differ between direct and pooled connections; do not assemble or interchange them manually. Percent-encode reserved characters in a password when required by the URL format.

- **Recommended for a persistent Render backend on IPv4:** shared **session pooler**. Supabase documents this as the direct-connection alternative for IPv4-only networks.
- **Direct endpoint:** suitable when Render can reach the project's IPv6 endpoint, or the project has the applicable IPv4 add-on. If IPv6 is unreachable, use the supplied session-pooler URL; do not disable TLS or weaken network controls.
- **Transaction pooler:** supported by this implementation because automatic prepared statements are disabled (`prepare_threshold=None`), schema selection is transaction-local, advisory locks are transaction-scoped, and queries are not pipelined. No session state is assumed between operations. Prefer session mode for this persistent backend unless connection-budget requirements call for transaction mode.

For remote connections, the minimum TLS mode is `require`; `disable`, `allow`, and `prefer` are rejected. Stronger supplied settings such as `sslmode=verify-full` and `sslrootcert` are preserved. `require` encrypts but does not necessarily verify the server identity. For stronger protection, obtain the appropriate Supabase CA certificate, mount it securely on Render, and use the supplied endpoint with `sslmode=verify-full` and the correct `sslrootcert` path. Enable Supabase's server-side SSL enforcement where available. Only explicitly local loopback URLs may opt out with `sslmode=disable` for isolated local tests.

Reference: [Supabase connection options and TLS](https://supabase.com/docs/guides/database/connecting-to-postgres).

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

Use a dedicated backend database role, not a browser anon key or Supabase Data API key. At initial startup it needs permission to create the configured schema/tables/indexes, or ownership of a pre-provisioned empty schema. For a pre-provisioned schema, grant only the needed role access and ownership/CREATE rights. Subsequent operations need schema USAGE and table SELECT/INSERT/UPDATE/DELETE (repair updates replace child rows). This version initializes migrations during startup, so the configured role must continue to have the necessary DDL rights. Separate migration/runtime roles are not implemented here.

Do not expose the private Sentinel schema through Supabase's public Data API and do not grant anon/authenticated roles access to it. Sentinel uses a server-side SQL role; its API-key authentication is not a substitute for database-role isolation.

Initialization does not drop tables, truncate data, or copy SQLite data. If pre-existing conflicting tables exist in the configured schema without the migration record, initialization fails rather than silently adopting or altering them. Choose a clean private schema or review an explicit migration. Future schema changes should be added as new numbered, atomic migrations; do not alter an already-applied migration definition.

## Safe Tests

Unit tests and existing SQLite tests need no live Supabase connection. New PostgreSQL integration tests do nothing unless `TEST_POSTGRES_URL` is configured. Never use the production Supabase URL for this variable. Use a separate local test database or a dedicated non-production Supabase project/database and test role.

Each integration test creates a randomized `sentinel_test_<uuid>` schema, initializes the schema there, and drops only that test schema during cleanup. Before connecting, the guard resolves the application `DATABASE_URL` from the same Settings object used by the application, including `.env`. Matching host/database targets are rejected even if ports differ, and loopback aliases are treated as equivalent. Test URLs must explicitly identify a host and database. These conservative checks are a guard, not proof that differently named pooler/direct endpoints belong to different projects. You are responsible for supplying a genuinely non-production test endpoint. The test role needs CREATE schema and rights to delete its own isolated schema. No production data is copied or touched.

Set the test URL privately through a secret environment file/manager, not a literal command containing credentials. Then run:

```powershell
uv run pytest -q tests/integration/persistence/test_postgres.py
```

For repeatable local testing using the credentials already configured privately in `.env`, run:

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

All four existing repository contracts are implemented for PostgreSQL, including repair attempts, steps, and verifications. Autonomous repair is still disabled in the API. No SQLite-to-PostgreSQL data-transfer tool, Supabase Data API adapter, multi-operation unit of work for an entire investigation, or separate offline migration CLI is added. An investigation persists through the existing sequence of repository operations; individual operations and repair writes are atomic.

`/health` remains public and does not query the database. Startup requires successful database schema initialization; a failed startup prevents serving any routes until configuration/connectivity is corrected. Runtime PostgreSQL failures return a generic HTTP 503. Endpoint rate limiting remains per-process/in-memory and is not distributed across Render instances, matching existing behavior.

No Supabase resources are provisioned and no deployment, commit, or push is performed by this change. Live Supabase compatibility must be verified against a dedicated test database before deploying production.

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
- [src/sentinel/config/settings.py](../src/sentinel/config/settings.py): database schema/timeout/pool settings and exclude the URL from Settings representation.
- [src/sentinel/bootstrap/investigation.py](../src/sentinel/bootstrap/investigation.py): inject shared persistence while retaining legacy SQLite-path compatibility.
- [src/sentinel/bootstrap/application.py](../src/sentinel/bootstrap/application.py): accept both adapters or the shared bundle without enabling repair by default.
- [src/sentinel/api.py](../src/sentinel/api.py): own shared persistence lifecycle and return sanitized database failures. Security dependency implementations are unchanged.
- [src/sentinel/main.py](../src/sentinel/main.py): use the same selected persistence bundle in the CLI and a PostgreSQL-compatible selector loop, preserving its existing incident-creation output.
- [tests/unit/test_main.py](../tests/unit/test_main.py): isolate CLI persistence on temporary SQLite storage and verify PostgreSQL factory/lifecycle wiring without network access.
- [tests/unit/config/test_settings.py](../tests/unit/config/test_settings.py): verify database environment values and secret-safe Settings representation.
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

Local credentials are configured only in the ignored `.env`, using the supplied local server/database. No real credential values were added to tracked files. Domain models, application ports, API authentication/rate-limit implementations, and repair-safety policies remain unchanged.

## Local Validation Results

- `uv run ruff format --check .`: PASS, 252 files formatted.
- `uv run ruff check .`: PASS.
- `uv run mypy src`: PASS, 132 source files.
- `uv run pytest`: the first refactor run reported 255 passed, 5 skipped, and one existing live Ollama timeout; its unchanged isolated retry passed. See the final task report for the last full-suite result.
- `uv run python -m tests.fixtures.postgres`: PASS, 5 real PostgreSQL tests passed and the temporary local test database was removed.
- `uv lock --check`: PASS, 82 packages resolved.

The standard full suite leaves live PostgreSQL integrations opt-in unless `TEST_POSTGRES_URL` is configured. They were executed separately using the new local runner, not merely skipped: native UUID/JSONB/timestamp mapping, foreign keys, rollback, duplicate writes, concurrent migrations, atomic repair writes, and the investigation factory all passed against actual local PostgreSQL. Supabase transaction-pooler behavior and the production Supabase/Render endpoint remain unverified; local PostgreSQL testing is not a substitute for non-production Supabase validation.

The earlier missing-credential connection problem is resolved by restoring the supplied local credentials in the ignored environment file. The application database connection was verified read-only, and all destructive test cleanup was confined to randomized test databases and schemas.

An earlier full run hit the existing live planner integration's 60-second Ollama timeout (`LLMConnectionError: Ollama request timed out.`). The unchanged isolated retry and subsequent full suites passed. No LLM timeout, assertion, or existing test marker was changed.