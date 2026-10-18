import logging
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from sentinel.api import app as sentinel_app
from sentinel.api import register_api_error_handlers
from sentinel.infrastructure.database.postgres import DatabaseUnavailable
from sentinel.infrastructure.middleware import RequestIDMiddleware


def create_error_test_app(*, request_ids: bool = True) -> FastAPI:
    test_app = FastAPI()
    if request_ids:
        test_app.add_middleware(RequestIDMiddleware)
    register_api_error_handlers(test_app)

    @test_app.get("/unauthorized")
    async def unauthorized() -> None:
        raise HTTPException(status_code=401, detail="private-api-key")

    @test_app.get("/not-found")
    async def not_found() -> None:
        raise HTTPException(status_code=404, detail="private-resource-detail")

    @test_app.get("/limited")
    async def limited() -> None:
        raise HTTPException(
            status_code=429,
            detail="private-limit-detail",
            headers={"Retry-After": "17", "X-Custom-Error": "preserved"},
        )

    @test_app.get("/database-error")
    async def database_error() -> None:
        raise DatabaseUnavailable("postgresql://user:private-password@host/db")

    @test_app.get("/unexpected")
    async def unexpected() -> None:
        raise RuntimeError("private-request-body and private-password")

    @test_app.get("/validate")
    async def validate(value: int) -> dict[str, int]:
        return {"value": value}

    return test_app


def assert_error_envelope(response, *, code: str, status_code: int) -> dict[str, str]:
    assert response.status_code == status_code
    error = response.json()["error"]
    assert error["code"] == code
    assert error["message"]
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert str(UUID(error["request_id"])) == error["request_id"]
    return error


def test_http_authentication_and_not_found_errors_use_safe_contract() -> None:
    with TestClient(create_error_test_app()) as client:
        unauthorized = client.get("/unauthorized")
        missing = client.get("/missing-route")

    assert_error_envelope(unauthorized, code="AUTHENTICATION_FAILED", status_code=401)
    assert_error_envelope(missing, code="NOT_FOUND", status_code=404)
    assert "private-api-key" not in unauthorized.text


def test_validation_errors_use_safe_contract() -> None:
    with TestClient(create_error_test_app()) as client:
        response = client.get("/validate")

    assert_error_envelope(response, code="VALIDATION_ERROR", status_code=422)
    assert "detail" not in response.json()


def test_rate_limit_error_preserves_retry_after_and_other_headers() -> None:
    with TestClient(create_error_test_app()) as client:
        response = client.get("/limited")

    assert_error_envelope(response, code="RATE_LIMIT_EXCEEDED", status_code=429)
    assert response.headers["Retry-After"] == "17"
    assert response.headers["X-Custom-Error"] == "preserved"


def test_database_error_is_sanitized() -> None:
    with TestClient(create_error_test_app()) as client:
        response = client.get("/database-error")

    assert_error_envelope(response, code="DATABASE_UNAVAILABLE", status_code=503)
    assert "private-password" not in response.text
    assert "postgresql://" not in response.text


def test_unexpected_error_is_generic_logged_and_correlated(caplog) -> None:
    request_id = "550e8400-e29b-41d4-a716-446655440000"
    with (
        caplog.at_level(logging.ERROR, logger="sentinel.api"),
        TestClient(create_error_test_app(), raise_server_exceptions=False) as client,
    ):
        response = client.get("/unexpected", headers={"X-Request-ID": request_id})

    error = assert_error_envelope(
        response, code="INTERNAL_SERVER_ERROR", status_code=500
    )
    assert error["request_id"] == request_id
    assert "private-request-body" not in response.text
    assert "private-password" not in response.text
    assert "private-request-body" not in caplog.text
    assert "private-password" not in caplog.text
    record = next(
        record for record in caplog.records if record.levelno == logging.ERROR
    )
    assert record.getMessage() == "Unhandled API exception"
    assert record.exception_type == "RuntimeError"
    assert record.request_id == request_id
    assert record.exc_info is None


def test_error_handler_generates_request_id_without_middleware() -> None:
    with TestClient(create_error_test_app(request_ids=False)) as client:
        response = client.get("/unauthorized")

    assert_error_envelope(response, code="AUTHENTICATION_FAILED", status_code=401)


def test_openapi_documents_standard_error_envelope() -> None:
    operation = sentinel_app.openapi()["paths"]["/incidents"]["post"]
    response_schema = operation["responses"]["422"]["content"]["application/json"][
        "schema"
    ]

    assert response_schema["$ref"].endswith("/APIErrorResponse")
    error_schema = sentinel_app.openapi()["components"]["schemas"]["APIErrorDetail"]
    assert set(error_schema["properties"]) == {"code", "message", "request_id"}
