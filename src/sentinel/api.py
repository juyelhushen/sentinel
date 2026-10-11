import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from sentinel.application.use_cases.create_incident import (
    CreateIncidentCommand,
    CreateIncidentUseCase,
)
from sentinel.bootstrap.investigation import create_investigation_service
from sentinel.config.settings import get_settings
from sentinel.domain.models.incident import Incident
from sentinel.infrastructure.database.sqlite import SQLiteDatabase
from sentinel.infrastructure.dependencies.llm import create_llm_provider
from sentinel.infrastructure.persistence.sqllite.incident_repository import (
    SQLiteIncidentRepository,
)


class CreateIncidentRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=5000)


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
    prefix = "sqlite:///"

    if not database_url.startswith(prefix):
        raise RuntimeError("Only SQLite database URLs are supported.")

    raw_path = database_url.removeprefix(prefix)
    path = Path(raw_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()

    repository_root = settings.repository_root.resolve()
    repository_root.mkdir(parents=True, exist_ok=True)

    database_path = resolve_database_path(settings.database_url)
    llm_provider = create_llm_provider()

    investigation_service = create_investigation_service(
        llm_provider=llm_provider,
        repository_root=repository_root,
        database_path=database_path,
    )

    database = SQLiteDatabase(database_path)
    incident_repository = SQLiteIncidentRepository(database)

    app.state.settings = settings
    app.state.llm_provider = llm_provider
    app.state.incident_repository = incident_repository
    app.state.create_incident = CreateIncidentUseCase(incident_repository)
    app.state.investigation_service = investigation_service

    yield


app = FastAPI(
    title="Sentinel",
    description="Autonomous Multi-Agent Engineering Ops Copilot",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "sentinel"}


@app.get(
    "/health/ollama",
    dependencies=[Depends(require_api_key)],
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
    dependencies=[Depends(require_api_key)],
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
    dependencies=[Depends(require_api_key)],
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
