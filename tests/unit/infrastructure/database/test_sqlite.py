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

    assert database.database_path() == database_path