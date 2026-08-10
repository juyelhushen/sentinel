import sqlite3

from sentinel.config.settings import get_settings
from sentinel.infrastructure.persistence.database import (
    create_connection,
)
from sentinel.infrastructure.persistence.models import initialize_database


def create_database_connection() -> sqlite3.Connection:
    """Create and initialize the application database."""

    settings = get_settings()

    connection = create_connection(settings.database_url)

    initialize_database(connection)

    return connection
