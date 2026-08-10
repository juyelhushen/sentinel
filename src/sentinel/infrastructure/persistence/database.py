import sqlite3
from pathlib import Path


def create_connection(database_url: str) -> sqlite3.Connection:
    """Create a SQLite database connection to a SQLite database."""

    if not database_url.startswith("sqlite:///"):
        raise ValueError("Invalid sql database URL. Must start with 'sqlite:///'.")

    database_path = database_url.removeprefix("sqlite:///")

    path = Path(database_path)

    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)

    connection.row_factory = sqlite3.Row

    return connection
