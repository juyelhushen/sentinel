import sqlite3

from sentinel.infrastructure.database.sqlite import SQLiteDatabase


def test_connect_enables_foreign_keys(tmp_path):
    database = SQLiteDatabase(tmp_path / "sentinel.db")

    connection = database.connect()

    try:
        result = connection.execute("PRAGMA foreign_keys").fetchone()

        assert result == (1,)
    finally:
        connection.close()


def test_database_path_is_exposed(tmp_path):
    database_path = tmp_path / "sentinel.db"

    database = SQLiteDatabase(database_path)

    assert database.database_path == database_path

def test_transaction_commits_on_success(tmp_path):
    database = SQLiteDatabase(tmp_path / "sentinel.db")

    with database.connect() as connection:
        connection.execute(
            "CREATE TABLE test_data (value TEXT)"
        )

    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO test_data (value) VALUES (?)",
            ("committed",),
        )

    with database.connect() as connection:
        result = connection.execute(
            "SELECT value FROM test_data"
        ).fetchone()

    assert result == ("committed",)


def test_transaction_rolls_back_on_failure(tmp_path):
    database = SQLiteDatabase(tmp_path / "sentinel.db")

    with database.connect() as connection:
        connection.execute(
            "CREATE TABLE test_data (value TEXT)"
        )

    try:
        with database.transaction() as connection:
            connection.execute(
                "INSERT INTO test_data (value) VALUES (?)",
                ("rolled-back",),
            )
            raise RuntimeError("simulated failure")
    except RuntimeError:
        pass

    with database.connect() as connection:
        result = connection.execute(
            "SELECT value FROM test_data"
        ).fetchone()

    assert result is None