from psycopg import sql

from sentinel.infrastructure.database.postgres import PostgreSQLDatabase

_INITIAL_SCHEMA = (
    """
    CREATE TABLE incidents (
        id UUID PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        repository TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE executions (
        id UUID PRIMARY KEY,
        incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
        status TEXT NOT NULL,
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ
    )
    """,
    "CREATE INDEX idx_executions_incident_id ON executions(incident_id)",
    """
    CREATE TABLE tool_executions (
        request_id UUID PRIMARY KEY,
        execution_id UUID,
        tool_name TEXT NOT NULL,
        status TEXT NOT NULL,
        arguments JSONB NOT NULL,
        output TEXT,
        error TEXT,
        started_at TIMESTAMPTZ NOT NULL,
        completed_at TIMESTAMPTZ
    )
    """,
    "CREATE INDEX idx_tool_executions_execution_id ON tool_executions(execution_id)",
    """
    CREATE TABLE repair_attempts (
        id UUID PRIMARY KEY,
        repair_plan_id UUID NOT NULL,
        execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
        attempt_number INTEGER NOT NULL,
        plan_summary TEXT NOT NULL,
        approval_status TEXT,
        approval_reason TEXT,
        execution_error TEXT,
        created_at TIMESTAMPTZ NOT NULL,
        UNIQUE (execution_id, attempt_number)
    )
    """,
    "CREATE INDEX idx_repair_attempts_execution_id ON repair_attempts(execution_id)",
    """
    CREATE TABLE repair_steps (
        id UUID PRIMARY KEY,
        repair_attempt_id UUID NOT NULL REFERENCES repair_attempts(id) ON DELETE CASCADE,
        step_number INTEGER NOT NULL,
        action TEXT NOT NULL,
        file_path TEXT NOT NULL,
        description TEXT NOT NULL,
        patch TEXT NOT NULL
    )
    """,
    "CREATE INDEX idx_repair_steps_attempt_id ON repair_steps(repair_attempt_id)",
    """
    CREATE TABLE verifications (
        id UUID PRIMARY KEY,
        repair_attempt_id UUID NOT NULL REFERENCES repair_attempts(id) ON DELETE CASCADE,
        status TEXT NOT NULL,
        summary TEXT NOT NULL,
        test_output TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL
    )
    """,
    "CREATE INDEX idx_verifications_attempt_id ON verifications(repair_attempt_id)",
)


async def initialize_postgres_schema(database: PostgreSQLDatabase) -> None:
    """Apply versioned, atomic migrations under a cross-process lock."""
    async with database.connection(select_schema=False) as connection:
        await connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"sentinel-schema:{database.schema}",),
        )
        await connection.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(database.schema)
            )
        )
        await connection.execute(
            "SELECT set_config('search_path', %s, true)",
            (f'"{database.schema}", pg_catalog',),
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor = await connection.execute("SELECT version FROM schema_migrations")
        versions = {row["version"] for row in await cursor.fetchall()}
        if versions - {1}:
            raise RuntimeError("Database schema is newer than this Sentinel version.")
        if 1 not in versions:
            for statement in _INITIAL_SCHEMA:
                await connection.execute(statement)
            await connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)", (1,)
            )
