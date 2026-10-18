import asyncio
from types import SimpleNamespace

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

from sentinel import api
from sentinel.infrastructure.metrics import HTTPMetrics
from sentinel.infrastructure.middleware import RequestIDMiddleware

API_KEY = "metrics-test-key"


def create_metrics_test_app(metrics: HTTPMetrics) -> FastAPI:
    test_app = FastAPI()
    test_app.state.settings = SimpleNamespace(api_key=SecretStr(API_KEY))
    test_app.state.http_metrics = metrics
    test_app.add_middleware(RequestIDMiddleware, metrics=metrics)
    api.register_api_error_handlers(test_app)

    @test_app.get("/items/{item_id}")
    async def item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    @test_app.get("/slow")
    async def slow() -> dict[str, str]:
        await asyncio.sleep(0.02)
        return {"status": "ok"}

    @test_app.get("/in-progress")
    async def in_progress() -> str:
        return metrics.render()

    @test_app.get("/limited")
    async def limited() -> None:
        raise HTTPException(
            status_code=429,
            detail="private-limit-detail",
            headers={"Retry-After": "17"},
        )

    test_app.add_api_route(
        "/metrics",
        api.metrics,
        methods=["GET"],
        dependencies=[Depends(api.require_api_key)],
    )
    return test_app


def scrape(client: TestClient) -> str:
    response = client.get("/metrics", headers={"X-API-Key": API_KEY})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    return response.text


def test_metrics_endpoint_requires_api_key_and_uses_error_envelope() -> None:
    with TestClient(create_metrics_test_app(HTTPMetrics())) as client:
        response = client.get("/metrics")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_FAILED"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


def test_metrics_count_requests_errors_duration_and_in_progress() -> None:
    metrics = HTTPMetrics()
    with TestClient(create_metrics_test_app(metrics)) as client:
        success = client.get("/items/incident-secret")
        assert success.status_code == 200
        slow_response = client.get("/slow")
        assert slow_response.status_code == 200
        in_progress = client.get("/in-progress")
        assert "sentinel_http_requests_in_progress 1" in in_progress.text
        scrape(client)
        missing = client.get("/missing")
        assert missing.status_code == 404
        output = scrape(client)
        completed_output = metrics.render()

    assert (
        'sentinel_http_requests_total{method="GET",route="/items/{item_id}",status="200"} 1'
        in output
    )
    assert (
        'sentinel_http_requests_total{method="GET",route="unmatched",status="404"} 1'
        in output
    )
    assert (
        'sentinel_http_request_duration_seconds_count{method="GET",route="/slow"} 1'
        in output
    )
    assert (
        'sentinel_http_request_duration_seconds_sum{method="GET",route="/slow"}'
        in output
    )
    assert "sentinel_http_request_duration_seconds_bucket" in output
    assert "sentinel_http_requests_in_progress 0" in output
    assert "sentinel_http_requests_in_progress 0" in completed_output
    assert 'route="/metrics"' not in output
    assert "incident-secret" not in output
    assert "X-API-Key" not in output


def test_metrics_count_429_responses_and_do_not_expose_request_data() -> None:
    metrics = HTTPMetrics()
    with TestClient(create_metrics_test_app(metrics)) as client:
        limited = client.get("/limited?credential=private-query")
        assert limited.status_code == 429
        assert limited.headers["Retry-After"] == "17"
        assert "private-limit-detail" not in limited.text
        output = scrape(client)

    assert (
        'sentinel_http_rate_limit_rejections_total{method="GET",route="/limited"} 1'
        in output
    )
    assert (
        'sentinel_http_requests_total{method="GET",route="/limited",status="429"} 1'
        in output
    )
    assert "private-query" not in output
    assert "private-limit-detail" not in output
