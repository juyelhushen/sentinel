import asyncio
import hashlib
import logging
import secrets
from asyncio import Lock
from collections import deque
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic, perf_counter
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from psycopg import Error as PostgreSQLError
from pydantic import BaseModel, Field

from sentinel.application.use_cases.create_incident import (
    CreateIncidentCommand,
    CreateIncidentUseCase,
)
from sentinel.bootstrap.investigation import create_investigation_service
from sentinel.bootstrap.persistence import open_persistence
from sentinel.bootstrap.persistence import resolve_database_path as resolve_sqlite_path
from sentinel.config.settings import get_settings
from sentinel.domain.models.incident import Incident
from sentinel.infrastructure.database.postgres import (
    DatabaseUnavailable,
    PostgreSQLDatabase,
)
from sentinel.infrastructure.database.sqlite import SQLiteDatabase
from sentinel.infrastructure.dependencies.llm import create_llm_provider
from sentinel.infrastructure.logging_config import configure_logging
from sentinel.infrastructure.request_context import request_id_context

logger = logging.getLogger("sentinel.api")


class CreateIncidentRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=5000)


class InMemoryRateLimiter:
    """Limit requests per API key and endpoint."""

    def __init__(self) -> None:
        self._requests: dict[tuple[str, str], deque[float]] = {}
        self._lock = Lock()

    async def check(
        self,
        api_key: str,
        endpoint: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> None:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        bucket_key = (key_hash, endpoint)

        async with self._lock:
            now = monotonic()
            timestamps = self._requests.setdefault(
                bucket_key,
                deque(),
            )

            while timestamps and now - timestamps[0] >= window_seconds:
                timestamps.popleft()

            if len(timestamps) >= max_requests:
                retry_after = max(
                    1,
                    int(window_seconds - (now - timestamps[0])),
                )
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Try again later.",
                    headers={"Retry-After": str(retry_after)},
                )

            timestamps.append(now)


class RateLimitDependency:
    """FastAPI dependency for endpoint-specific rate limits."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: int = 60,
    ) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds

    async def __call__(
        self,
        request: Request,
        api_key: str | None = Header(
            default=None,
            alias="X-API-Key",
        ),
    ) -> None:
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="Missing API key.",
            )

        route = request.scope.get("route")
        endpoint = getattr(route, "path", request.url.path)

        limiter: InMemoryRateLimiter = request.app.state.rate_limiter

        await limiter.check(
            api_key=api_key,
            endpoint=f"{request.method}:{endpoint}",
            max_requests=self._max_requests,
            window_seconds=self._window_seconds,
        )


api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
)


async def require_api_key(
    request: Request,
    api_key: str | None = Depends(api_key_header),
) -> None:
    configured_key = request.app.state.settings.api_key

    if configured_key is None or not configured_key.get_secret_value().strip():
        raise HTTPException(
            status_code=503,
            detail="API authentication is not configured.",
        )

    expected_key = configured_key.get_secret_value()

    if api_key is None or not secrets.compare_digest(
        api_key,
        expected_key,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key.",
        )


def resolve_database_path(database_url: str) -> Path:
    """Resolve the configured SQLite URL to a filesystem path."""
    return resolve_sqlite_path(database_url)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()

    repository_root = settings.repository_root.resolve()
    repository_root.mkdir(parents=True, exist_ok=True)

    llm_provider = create_llm_provider()

    async with open_persistence(
        settings.database_connection_url,
        schema=settings.database_schema,
        timeout_seconds=settings.database_connect_timeout_seconds,
        pool_size=settings.database_pool_size,
    ) as persistence:
        investigation_service = create_investigation_service(
            llm_provider=llm_provider,
            repository_root=repository_root,
            persistence=persistence,
        )
        app.state.database = persistence.database
        app.state.settings = settings
        app.state.llm_provider = llm_provider
        app.state.incident_repository = persistence.incidents
        app.state.create_incident = CreateIncidentUseCase(persistence.incidents)
        app.state.investigation_service = investigation_service
        app.state.rate_limiter = InMemoryRateLimiter()
        yield


configure_logging()

app = FastAPI(
    title="Sentinel",
    description="Autonomous Multi-Agent Engineering Ops Copilot",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_id_middleware(
    request: Request,
    call_next: Any,
):
    incoming_request_id = request.headers.get("X-Request-ID")

    try:
        request_id = (
            str(UUID(incoming_request_id)) if incoming_request_id else str(uuid4())
        )
    except ValueError:
        request_id = str(uuid4())

    request.state.request_id = request_id
    token = request_id_context.set(request_id)
    start_time = perf_counter()

    try:
        response = await call_next(request)

        duration_ms = round((perf_counter() - start_time) * 1000, 2)

        logger.info(
            "HTTP request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response

    except Exception:
        logger.exception(
            "Unhandled exception during HTTP request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
            },
        )
        raise

    finally:
        request_id_context.reset(token)


@app.exception_handler(DatabaseUnavailable)
@app.exception_handler(PostgreSQLError)
async def database_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database unavailable. Try again later."},
    )


@app.get("/health")
async def health(
    request_id: Annotated[
        str | None,
        Header(alias="X-Request-ID"),
    ] = None,
) -> dict[str, str]:
    return {"status": "ok", "service": "sentinel"}


@app.get(
    "/health/ollama",
    dependencies=[
        Depends(require_api_key),
        Depends(RateLimitDependency(max_requests=10)),
    ],
)
async def ollama_health(request: Request) -> dict[str, str]:
    provider = request.app.state.llm_provider

    if not await provider.health_check():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama is unavailable.",
        )

    return {"status": "ok", "provider": "ollama"}


@app.post(
    "/incidents",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_api_key),
        Depends(RateLimitDependency(max_requests=10)),
    ],
)
async def create_incident(
    payload: CreateIncidentRequest,
    request: Request,
) -> dict[str, Any]:
    settings = request.app.state.settings

    command = CreateIncidentCommand(
        title=payload.title,
        description=payload.description,
        repository=str(settings.repository_root.resolve()),
    )

    incident: Incident = await request.app.state.create_incident.execute(command)

    return {
        "id": str(incident.id),
        "title": incident.title,
        "description": incident.description,
        "repository": incident.repository,
        "status": incident.status.value,
        "created_at": incident.created_at.isoformat(),
    }


@app.post(
    "/incidents/{incident_id}/investigate",
    dependencies=[
        Depends(require_api_key),
        Depends(RateLimitDependency(max_requests=10)),
    ],
)
async def investigate_incident(
    incident_id: UUID,
    request: Request,
) -> dict[str, Any]:
    try:
        result = await request.app.state.investigation_service.investigate(incident_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    incident = result.get("incident")
    execution = result.get("execution")

    return {
        "incident_id": str(incident.id) if incident else str(incident_id),
        "incident_status": (incident.status.value if incident else "unknown"),
        "execution_id": str(execution.id) if execution else None,
        "execution_status": (execution.status.value if execution else None),
        "error": result.get("error"),
    }


@app.get("/health/ready")
async def readiness(request: Request) -> dict[str, str]:
    """Check whether Sentinel can access its database."""
    database = request.app.state.database

    if isinstance(database, PostgreSQLDatabase):
        async with database.connection() as connection:
            await connection.execute("SELECT 1")
    elif isinstance(database, SQLiteDatabase):

        def check_sqlite() -> None:
            with database.connect() as connection:
                connection.execute("SELECT 1")

        await asyncio.to_thread(check_sqlite)
    else:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Try again later.",
        )

    return {"status": "ready", "database": "ok"}
