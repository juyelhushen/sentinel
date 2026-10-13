from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from sentinel.api import request_id_context, request_id_middleware


def create_test_app() -> FastAPI:
    """Create a lightweight app using Sentinel's request ID middleware."""
    test_app = FastAPI()
    test_app.middleware("http")(request_id_middleware)

    @test_app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @test_app.get("/request-context")
    async def request_context(request: Request) -> dict[str, str]:
        return {
            "request_id": request.state.request_id,
            "context_id": request_id_context.get(),
        }

    return test_app


def test_generates_request_id_when_header_is_missing() -> None:
    with TestClient(create_test_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200

    request_id = response.headers["X-Request-ID"]
    assert str(UUID(request_id)) == request_id


def test_preserves_valid_request_id() -> None:
    request_id = "550e8400-e29b-41d4-a716-446655440000"

    with TestClient(create_test_app()) as client:
        response = client.get(
            "/health",
            headers={"X-Request-ID": request_id},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


def test_replaces_invalid_request_id() -> None:
    with TestClient(create_test_app()) as client:
        response = client.get(
            "/health",
            headers={"X-Request-ID": "invalid-id"},
        )

    assert response.status_code == 200

    request_id = response.headers["X-Request-ID"]
    assert str(UUID(request_id)) == request_id
    assert request_id != "invalid-id"


def test_request_id_is_available_in_request_context() -> None:
    with TestClient(create_test_app()) as client:
        response = client.get("/request-context")

    assert response.status_code == 200

    body = response.json()
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert body["context_id"] == body["request_id"]
