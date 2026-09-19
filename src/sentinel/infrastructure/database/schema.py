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
                """
            )