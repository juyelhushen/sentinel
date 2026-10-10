from sentinel.infrastructure.database.sqlite import SQLiteDatabase


class SchemaInitializer:
    """Creates the Sentinel database schema."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def initialize(self) -> None:
        with self._database.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY (incident_id)
                        REFERENCES incidents(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_executions_incident_id
                    ON executions(incident_id);

                CREATE TABLE IF NOT EXISTS tool_executions (
                    request_id TEXT PRIMARY KEY,
                    execution_id TEXT,
                    tool_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    arguments TEXT NOT NULL,
                    output TEXT,
                    error TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_tool_executions_execution_id
                    ON tool_executions(execution_id);

                CREATE TABLE IF NOT EXISTS repair_attempts (
                    id TEXT PRIMARY KEY,
                    repair_plan_id TEXT NOT NULL,
                    execution_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    plan_summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (execution_id)
                        REFERENCES executions(id)
                        ON DELETE CASCADE,
                    UNIQUE (execution_id, attempt_number)
                );

                CREATE INDEX IF NOT EXISTS idx_repair_attempts_execution_id
                    ON repair_attempts(execution_id);

                CREATE TABLE IF NOT EXISTS repair_steps (
                    id TEXT PRIMARY KEY,
                    repair_attempt_id TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    description TEXT NOT NULL,
                    patch TEXT NOT NULL,
                    FOREIGN KEY (repair_attempt_id)
                        REFERENCES repair_attempts(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_repair_steps_attempt_id
                   ON repair_steps(repair_attempt_id);

                CREATE TABLE IF NOT EXISTS verifications (
                   id TEXT PRIMARY KEY,
                   repair_attempt_id TEXT NOT NULL,
                   status TEXT NOT NULL,
                   summary TEXT NOT NULL,
                   test_output TEXT NOT NULL,
                   created_at TEXT NOT NULL,
                   FOREIGN KEY (repair_attempt_id)
                       REFERENCES repair_attempts(id)
                       ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_verifications_attempt_id
                  ON verifications(repair_attempt_id);
                """
            )

            self._migrate_repair_schema(connection)

    def _migrate_repair_schema(self, connection) -> None:
        columns = {
            column[1]: column
            for column in connection.execute("PRAGMA table_info('repair_attempts')").fetchall()
        }

        if "repair_plan_id" not in columns:
            connection.execute(
                "ALTER TABLE repair_attempts ADD COLUMN repair_plan_id TEXT"
            )

        if "plan_summary" not in columns:
            connection.execute(
                "ALTER TABLE repair_attempts ADD COLUMN plan_summary TEXT"
            )

        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_repair_attempts_execution_attempt_number ON repair_attempts(execution_id, attempt_number)"
        )

        connection.execute(
            "UPDATE repair_attempts SET repair_plan_id = id WHERE repair_plan_id IS NULL"
        )
        connection.execute(
            "UPDATE repair_attempts SET plan_summary = '' WHERE plan_summary IS NULL"
        )
