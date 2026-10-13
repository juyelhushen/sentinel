import json
import logging

from sentinel.infrastructure.logging_config import JsonFormatter
from sentinel.infrastructure.request_context import request_id_context


def test_json_formatter_includes_structured_http_fields() -> None:
    request_id = "550e8400-e29b-41d4-a716-446655440000"
    token = request_id_context.set(request_id)

    try:
        record = logging.LogRecord(
            name="sentinel.api",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="HTTP request completed",
            args=(),
            exc_info=None,
        )
        record.method = "GET"
        record.path = "/health"
        record.status_code = 200
        record.duration_ms = 12.5

        output = JsonFormatter().format(record)
        log_entry = json.loads(output)

        assert log_entry["level"] == "INFO"
        assert log_entry["logger"] == "sentinel.api"
        assert log_entry["message"] == "HTTP request completed"
        assert log_entry["request_id"] == request_id
        assert log_entry["method"] == "GET"
        assert log_entry["path"] == "/health"
        assert log_entry["status_code"] == 200
        assert log_entry["duration_ms"] == 12.5
        assert "timestamp" in log_entry
    finally:
        request_id_context.reset(token)


def test_json_formatter_omits_unprovided_http_fields() -> None:
    record = logging.LogRecord(
        name="sentinel.api",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Application started",
        args=(),
        exc_info=None,
    )

    log_entry = json.loads(JsonFormatter().format(record))

    assert log_entry["message"] == "Application started"
    assert "status_code" not in log_entry
    assert "duration_ms" not in log_entry


def test_json_formatter_includes_exception_details() -> None:
    try:
        raise ValueError("Example failure")
    except ValueError:
        record = logging.LogRecord(
            name="sentinel.api",
            level=logging.ERROR,
            pathname=__file__,
            lineno=10,
            msg="Unhandled exception during HTTP request",
            args=(),
            exc_info=__import__("sys").exc_info(),
        )

    output = JsonFormatter().format(record)
    log_entry = json.loads(output)

    assert "exception" in log_entry
    assert "ValueError: Example failure" in log_entry["exception"]
