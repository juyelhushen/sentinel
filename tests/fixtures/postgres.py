import asyncio
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest
from psycopg import ProgrammingError, sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from sentinel.config.settings import get_settings


def validate_test_target(test_url: str) -> None:
    application_url = get_settings().database_url
    try:
        test_parameters = conninfo_to_dict(test_url)
        application_parameters = (
            conninfo_to_dict(application_url)
            if application_url.startswith(("postgres://", "postgresql://"))
            else None
        )
    except ProgrammingError:
        pytest.fail("Invalid PostgreSQL test connection configuration.", pytrace=False)

    if not test_parameters.get("host") or not test_parameters.get("dbname"):
        pytest.fail(
            "TEST_POSTGRES_URL must name an explicit host and test database.",
            pytrace=False,
        )
    if application_parameters is None:
        return

    test_host = test_parameters["host"].lower().rstrip(".")
    application_host = application_parameters.get("host", "").lower().rstrip(".")
    loopback_hosts = {"localhost", "127.0.0.1", "::1"}
    same_host = test_host == application_host or (
        test_host in loopback_hosts and application_host in loopback_hosts
    )
    if same_host and test_parameters["dbname"] == application_parameters.get("dbname"):
        pytest.fail(
            "TEST_POSTGRES_URL must target a separate test database, not DATABASE_URL.",
            pytrace=False,
        )


@contextmanager
def isolated_local_database() -> Iterator[None]:
    settings = get_settings()
    parameters = conninfo_to_dict(settings.database_url)
    if parameters.get("host") not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError(
            "Local PostgreSQL tests require a loopback database endpoint."
        )
    name = f"sentinel_verify_{uuid4().hex}"
    previous = {
        key: os.environ.get(key) for key in ("DATABASE_URL", "TEST_POSTGRES_URL")
    }
    with psycopg.connect(
        settings.database_url, autocommit=True, connect_timeout=5
    ) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            os.environ["DATABASE_URL"] = settings.database_url
            os.environ["TEST_POSTGRES_URL"] = make_conninfo(
                settings.database_url, dbname=name
            )
            validate_test_target(os.environ["TEST_POSTGRES_URL"])
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def main() -> int:
    """Run PostgreSQL contracts in a temporary local database, never Supabase."""
    selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if sys.platform == "win32" and selector_policy is not None:
        asyncio.set_event_loop_policy(selector_policy())
    try:
        with isolated_local_database():
            print("Running contracts in an isolated local PostgreSQL database.")
            result = pytest.main(
                ["-q", "tests/integration/persistence/test_postgres.py"]
            )
        print("Isolated local PostgreSQL test database removed.")
        return int(result)
    except psycopg.Error, RuntimeError:
        print(
            "Local PostgreSQL test setup or cleanup failed; connection details withheld."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
