from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from psycopg import OperationalError

from sentinel import api
from sentinel.config.settings import Settings
from sentinel.llm.models import LLMResponse


@pytest.fixture
def configured_api(monkeypatch, tmp_path: Path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'sentinel.db'}",
        SENTINEL_API_KEY="unit-test-api-key",
        SENTINEL_REPOSITORY_ROOT=tmp_path,
    )
    provider = Mock()
    provider.health_check = AsyncMock(return_value=True)
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            content='{"summary": "No investigation steps", "steps": []}',
            model="test-model",
        )
    )
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    monkeypatch.setattr(api, "create_llm_provider", lambda: provider)
    return api.app


async def test_database_lifecycle_preserves_api_authentication_and_rate_limits(
    configured_api,
) -> None:
    async with (
        api.lifespan(configured_api),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=configured_api), base_url="http://test"
        ) as client,
    ):
        assert (await client.get("/health")).status_code == 200
        for headers in ({}, {"X-API-Key": "wrong-key"}):
            assert (
                await client.get("/health/ollama", headers=headers)
            ).status_code == 401
            assert (
                await client.post(
                    "/incidents",
                    json={"title": "Failure", "description": "Tests failed"},
                    headers=headers,
                )
            ).status_code == 401
        headers = {"X-API-Key": "unit-test-api-key"}
        for _ in range(10):
            assert (
                await client.get("/health/ollama", headers=headers)
            ).status_code == 200
        limited = await client.get("/health/ollama", headers=headers)
        assert limited.status_code == 429
        assert int(limited.headers["Retry-After"]) >= 1
        created = await client.post(
            "/incidents",
            headers=headers,
            json={"title": "Failure", "description": "Tests failed"},
        )
        assert created.status_code == 201
        incident_id = created.json()["id"]
        assert (
            await client.post(f"/incidents/{incident_id}/investigate")
        ).status_code == 401
        investigated = await client.post(
            f"/incidents/{incident_id}/investigate", headers=headers
        )
        assert investigated.status_code == 200
        assert investigated.json()["execution_status"] == "completed"
        assert (await client.get("/health")).status_code == 200


async def test_api_database_errors_do_not_expose_connection_details(
    configured_api,
) -> None:
    async with (
        api.lifespan(configured_api),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=configured_api), base_url="http://test"
        ) as client,
    ):
        configured_api.state.create_incident.execute = AsyncMock(
            side_effect=OperationalError("postgresql://user:secret@private-host/db")
        )
        result = await client.post(
            "/incidents",
            headers={"X-API-Key": "unit-test-api-key"},
            json={"title": "Failure", "description": "Tests failed"},
        )
        assert result.status_code == 503
        assert result.json() == {"detail": "Database unavailable. Try again later."}
        assert "secret" not in result.text
        assert "private-host" not in result.text
