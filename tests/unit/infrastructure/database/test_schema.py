from sentinel.infrastructure.database.schema import SchemaInitializer
from sentinel.infrastructure.database.sqlite import SQLiteDatabase


def test_initialize_creates_all_tables(tmp_path):
    database = SQLiteDatabase(tmp_path / "sentinel.db")
    initializer = SchemaInitializer(database)

    initializer.initialize()

    with database.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

    assert "incidents" in tables
    assert "executions" in tables
    assert "tool_executions" in tables


def test_initialize_is_idempotent(tmp_path):
    database = SQLiteDatabase(tmp_path / "sentinel.db")
    initializer = SchemaInitializer(database)

    initializer.initialize()
    initializer.initialize()

    with database.connect() as connection:
        result = connection.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table'
            AND name IN (
                'incidents',
                'executions',
                'tool_executions'
            )
            """
        ).fetchone()

    assert result == (3,)


def test_foreign_keys_are_enabled(tmp_path):
    database = SQLiteDatabase(tmp_path / "sentinel.db")
    initializer = SchemaInitializer(database)

    initializer.initialize()

    with database.connect() as connection:
        result = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()

    assert result == (1,)