import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    repository TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

def initialize_database(connection: sqlite3.Connection) -> None:
    """Initialize the Sentinel database schema."""
    connection.executescript(SCHEMA)
    connection.commit()
