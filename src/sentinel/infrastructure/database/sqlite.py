import sqlite3
from pathlib import Path


class SQLiteDatabase:
    """Manages the SQLite database connection and shared configuration."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    def database_path(self) -> Path:
        return self._database_path