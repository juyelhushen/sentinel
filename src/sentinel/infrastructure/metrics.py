from threading import Lock
from typing import Final

from starlette.types import Scope

HTTP_METHODS: Final = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
)
METRICS_PATH: Final = "/metrics"
HISTOGRAM_BUCKETS: Final = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)


def normalize_method(method: str) -> str:
    return method if method in HTTP_METHODS else "OTHER"


def route_template(scope: Scope) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) and path.startswith("/") else "unmatched"


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(**values: str) -> str:
    return (
        "{"
        + ",".join(f'{name}="{_escape_label(value)}"' for name, value in values.items())
        + "}"
    )


class HTTPMetrics:
    """Thread-safe, process-local HTTP metrics with bounded label values."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: dict[tuple[str, str, int], int] = {}
        self._rate_limit_rejections: dict[tuple[str, str], int] = {}
        self._duration_counts: dict[tuple[str, str], list[int]] = {}
        self._duration_sums: dict[tuple[str, str], float] = {}
        self._duration_totals: dict[tuple[str, str], int] = {}
        self._in_progress = 0

    def start_request(self) -> None:
        with self._lock:
            self._in_progress += 1

    def finish_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        duration = max(0.0, duration_seconds)
        request_key = (method, route, status_code)
        route_key = (method, route)

        with self._lock:
            self._in_progress = max(0, self._in_progress - 1)
            self._requests[request_key] = self._requests.get(request_key, 0) + 1
            if status_code == 429:
                self._rate_limit_rejections[route_key] = (
                    self._rate_limit_rejections.get(route_key, 0) + 1
                )

            bucket_counts = self._duration_counts.setdefault(
                route_key, [0] * len(HISTOGRAM_BUCKETS)
            )
            for index, upper_bound in enumerate(HISTOGRAM_BUCKETS):
                if duration <= upper_bound:
                    bucket_counts[index] += 1
            self._duration_sums[route_key] = (
                self._duration_sums.get(route_key, 0.0) + duration
            )
            self._duration_totals[route_key] = (
                self._duration_totals.get(route_key, 0) + 1
            )

    def render(self) -> str:
        with self._lock:
            requests = sorted(self._requests.items())
            rejections = sorted(self._rate_limit_rejections.items())
            duration_counts = {
                key: tuple(value) for key, value in self._duration_counts.items()
            }
            duration_sums = dict(self._duration_sums)
            duration_totals = dict(self._duration_totals)
            in_progress = self._in_progress

        lines = [
            "# HELP sentinel_http_requests_total Total observed HTTP requests, excluding metrics scrapes.",
            "# TYPE sentinel_http_requests_total counter",
        ]
        for (method, route, status_code), count in requests:
            lines.append(
                f"sentinel_http_requests_total{_labels(method=method, route=route, status=str(status_code))} {count}"
            )

        lines.extend(
            (
                "# HELP sentinel_http_request_duration_seconds HTTP request duration in seconds, excluding metrics scrapes.",
                "# TYPE sentinel_http_request_duration_seconds histogram",
            )
        )
        for method, route in sorted(duration_counts):
            bucket_counts = duration_counts[(method, route)]
            for upper_bound, count in zip(HISTOGRAM_BUCKETS, bucket_counts):
                lines.append(
                    f"sentinel_http_request_duration_seconds_bucket{_labels(method=method, route=route, le=str(upper_bound))} {count}"
                )
            lines.append(
                f"sentinel_http_request_duration_seconds_bucket{_labels(method=method, route=route, le='+Inf')} {duration_totals[(method, route)]}"
            )
            lines.append(
                f"sentinel_http_request_duration_seconds_sum{_labels(method=method, route=route)} {duration_sums[(method, route)]:.9f}"
            )
            lines.append(
                f"sentinel_http_request_duration_seconds_count{_labels(method=method, route=route)} {duration_totals[(method, route)]}"
            )

        lines.extend(
            (
                "# HELP sentinel_http_requests_in_progress Current in-progress HTTP requests.",
                "# TYPE sentinel_http_requests_in_progress gauge",
                f"sentinel_http_requests_in_progress {in_progress}",
                "# HELP sentinel_http_rate_limit_rejections_total HTTP 429 responses.",
                "# TYPE sentinel_http_rate_limit_rejections_total counter",
            )
        )
        for (method, route), count in rejections:
            lines.append(
                f"sentinel_http_rate_limit_rejections_total{_labels(method=method, route=route)} {count}"
            )

        return "\n".join(lines) + "\n"
