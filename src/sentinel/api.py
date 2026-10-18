import asyncio
import hashlib
import logging
import secrets
from asyncio import Lock
from collections import deque
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import APIKeyHeader
from psycopg import Error as PostgreSQLError
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from sentinel.application.ports.rate_limiter import RateLimitStore
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
from sentinel.infrastructure.metrics import METRICS_PATH, HTTPMetrics
from sentinel.infrastructure.middleware import (
    RequestIDMiddleware,
    SanitizedUnhandledError,
)
from sentinel.infrastructure.persistence.postgres.rate_limiter import (
    PostgreSQLRateLimitStore,
)
from sentinel.infrastructure.request_context import request_id_context

logger = logging.getLogger("sentinel.api")
http_metrics = HTTPMetrics()


class CreateIncidentRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=5000)


class APIErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class APIErrorResponse(BaseModel):
    error: APIErrorDetail


API_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    code: {"model": APIErrorResponse, "description": description}
    for code, description in (
        (401, "Authentication failed."),
        (404, "The requested resource was not found."),
        (422, "Request validation failed."),
        (429, "Rate limit exceeded."),
        (500, "An unexpected server error occurred."),
        (503, "A required service is unavailable."),
    )
}


def _request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if not request_id or request_id == "-":
        request_id = request_id_context.get()
    if not request_id or request_id == "-":
        request_id = str(uuid4())
    request.state.request_id = request_id
    return request_id


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    response_headers = {
        key: value
        for key, value in (headers or {}).items()
        if key.lower() != "x-request-id"
    }
    response_headers["X-Request-ID"] = request_id
    body = APIErrorResponse(
        error=APIErrorDetail(code=code, message=message, request_id=request_id)
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers=response_headers,
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise TypeError("Expected a Starlette HTTP exception.")
    safe_errors = {
        400: ("BAD_REQUEST", "The request could not be processed."),
        401: ("AUTHENTICATION_FAILED", "Authentication failed."),
        403: ("FORBIDDEN", "Access to this resource is forbidden."),
        404: ("NOT_FOUND", "The requested resource was not found."),
        422: ("VALIDATION_ERROR", "Request validation failed."),
        429: ("RATE_LIMIT_EXCEEDED", "Rate limit exceeded. Try again later."),
        503: ("SERVICE_UNAVAILABLE", "Service temporarily unavailable."),
    }
    code, message = safe_errors.get(
        exc.status_code,
        ("HTTP_ERROR", "The request could not be completed."),
    )
    if exc.status_code >= 500:
        code, message = "INTERNAL_SERVER_ERROR", "An internal server error occurred."
    return _error_response(
        request,
        status_code=exc.status_code,
        code=code,
        message=message,
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise TypeError("Expected a request validation error.")
    return _error_response(
        request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed.",
    )


async def database_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(
        request,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="DATABASE_UNAVAILABLE",
        message="Database unavailable. Try again later.",
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)
    exception_type = (
        exc.original_exception_type
        if isinstance(exc, SanitizedUnhandledError)
        else type(exc).__name__
    )
    logger.error(
        "Unhandled API exception",
        extra={
            "exception_type": exception_type,
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        },
    )
    return _error_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred.",
    )


def register_api_error_handlers(application: FastAPI) -> None:
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(
        RequestValidationError, validation_exception_handler
    )
    application.add_exception_handler(DatabaseUnavailable, database_error_handler)
    application.add_exception_handler(PostgreSQLError, database_error_handler)
    application.add_exception_handler(Exception, unexpected_error_handler)


class InMemoryRateLimiter:
    """Single-process sliding-window store for explicitly configured SQLite use."""

    def __init__(self) -> None:
        self._requests: dict[tuple[str, str], deque[float]] = {}
        self._lock = Lock()

    async def check_and_record(
        self,
        api_key: str,
        endpoint: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> int | None:
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
                return max(
                    1,
                    int(window_seconds - (now - timestamps[0])),
                )

            timestamps.append(now)
            return None

    async def check(
        self,
        api_key: str,
        endpoint: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> None:
        retry_after = await self.check_and_record(
            api_key, endpoint, max_requests, window_seconds
        )
        if retry_after is not None:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )


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

        limiter: RateLimitStore = request.app.state.rate_limiter

        retry_after = await limiter.check_and_record(
            api_key=api_key,
            endpoint=f"{request.method}:{endpoint}",
            max_requests=self._max_requests,
            window_seconds=self._window_seconds,
        )
        if retry_after is not None:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later.",
                headers={"Retry-After": str(retry_after)},
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
        if isinstance(persistence.database, PostgreSQLDatabase):
            app.state.rate_limiter = PostgreSQLRateLimitStore(persistence.database)
        elif isinstance(persistence.database, SQLiteDatabase):
            app.state.rate_limiter = InMemoryRateLimiter()
        else:
            raise TypeError("Unsupported database for rate limiting.")
        yield


configure_logging()

app = FastAPI(
    title="Sentinel",
    description="Autonomous Multi-Agent Engineering Ops Copilot",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware, metrics=http_metrics)
register_api_error_handlers(app)
app.state.http_metrics = http_metrics


@app.get(
    METRICS_PATH,
    response_class=PlainTextResponse,
    dependencies=[Depends(require_api_key)],
    responses=API_ERROR_RESPONSES,
)
async def metrics(request: Request) -> PlainTextResponse:
    """Expose process-local Prometheus metrics; requires the configured API key."""
    return PlainTextResponse(
        request.app.state.http_metrics.render(),
        media_type="text/plain; version=0.0.4",
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
    responses=API_ERROR_RESPONSES,
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
    responses=API_ERROR_RESPONSES,
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
    responses=API_ERROR_RESPONSES,
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


@app.get("/health/ready", responses=API_ERROR_RESPONSES)
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
