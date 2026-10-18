import logging
from time import perf_counter
from uuid import UUID, uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from sentinel.infrastructure.metrics import (
    METRICS_PATH,
    HTTPMetrics,
    normalize_method,
    route_template,
)
from sentinel.infrastructure.request_context import request_id_context

logger = logging.getLogger("sentinel.api")


class SanitizedUnhandledError(RuntimeError):
    def __init__(self, original_exception_type: str) -> None:
        super().__init__("Unhandled API exception.")
        self.original_exception_type = original_exception_type


class RequestIDMiddleware:
    """Attach request IDs and log HTTP request outcomes."""

    def __init__(self, app: ASGIApp, metrics: HTTPMetrics | None = None) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        incoming = headers.get(b"x-request-id", b"").decode("latin-1")

        try:
            request_id = str(UUID(incoming)) if incoming else str(uuid4())
        except ValueError:
            request_id = str(uuid4())

        token = request_id_context.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id

        start_time = perf_counter()
        status_code = 500
        method = normalize_method(scope.get("method", "OTHER"))
        record_metrics = self.metrics is not None and scope.get("path") != METRICS_PATH
        if record_metrics:
            assert self.metrics is not None
            self.metrics.start_request()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code

            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ]
                response_headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = response_headers

            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:  # noqa: BLE001
            raise SanitizedUnhandledError(type(exc).__name__) from None
        finally:
            duration_seconds = perf_counter() - start_time
            if record_metrics:
                assert self.metrics is not None
                self.metrics.finish_request(
                    method=method,
                    route=route_template(scope),
                    status_code=status_code,
                    duration_seconds=duration_seconds,
                )
            logger.info(
                "HTTP request completed",
                extra={
                    "request_id": request_id,
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status_code": status_code,
                    "duration_ms": round(duration_seconds * 1000, 2),
                },
            )
            request_id_context.reset(token)
