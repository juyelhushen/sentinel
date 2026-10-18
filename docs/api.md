# API Operations

## Monitoring and Observability

### Health Endpoints

Sentinel exposes three health-related routes with different scopes:

- `GET /health` is a public, shallow liveness-style response. It returns the
  service status and does not check the database or Ollama.
- `GET /health/ready` is a public readiness check for database access. It runs a
  simple database query and returns an error response if the database cannot be
  reached. It does not check Ollama.
- `GET /health/ollama` checks the Ollama provider. It requires `X-API-Key` and
  is rate limited; it is not a general application readiness check.

These routes are the health endpoints currently implemented by the API. In
particular, `/health` should not be interpreted as proof that dependent services
are ready.

### Prometheus Metrics

`GET /metrics` returns Prometheus text exposition format and requires the same
`X-API-Key` header as the protected API routes. The endpoint is included in the
OpenAPI document. Do not expose it to untrusted networks; operational metrics
can reveal traffic volume and route usage. Keep it behind authentication and
restrict scraping to a trusted monitoring system. Store the API key in a secret
manager or secret file; never put a real credential in Prometheus configuration,
dashboards, or examples.

The endpoint reports:

- `sentinel_http_requests_total`, grouped by normalized method, route template,
  and status code. Metrics requests themselves are excluded.
- `sentinel_http_request_duration_seconds`, a seconds histogram with cumulative
  buckets at 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, and 10
  seconds, plus `+Inf`, sum, and count series. Metrics requests are excluded.
- `sentinel_http_requests_in_progress`, a process-wide gauge that excludes
  metrics requests.
- `sentinel_http_rate_limit_rejections_total`, counting observed HTTP 429
  responses by method and route.

Route labels use FastAPI route templates; unmatched paths share the `unmatched`
label. Unknown methods are normalized to `OTHER`. No request IDs, API keys,
incident identifiers, query parameters, request bodies, or exception details
are used as metric labels. Updates are synchronized in memory. These metrics
are process-local and reset on process restart; they are not persisted or
automatically aggregated across application instances. If multiple instances
are deployed, a collector needs a way to scrape each instance separately for
reliable per-process counters and histograms. Scraping a load-balanced service
URL does not itself aggregate process-local state and may observe different
instances between scrapes.

Example PromQL queries (assuming the collector stores this endpoint's metrics):

Request rate across methods and routes:

```promql
sum by (method, route) (rate(sentinel_http_requests_total[5m]))
```

HTTP 5xx responses per second:

```promql
sum(rate(sentinel_http_requests_total{status=~"5.."}[5m]))
```

95th-percentile request duration in seconds, using the classic histogram buckets:

```promql
histogram_quantile(
  0.95,
  sum by (le) (rate(sentinel_http_request_duration_seconds_bucket[5m]))
)
```

The histogram has finite buckets only through 10 seconds; percentiles above that
range are limited by the `+Inf` bucket and should be interpreted accordingly.

### External Collector

A future Prometheus-compatible collector can scrape the HTTPS endpoint using
the existing API key. Keep the key in a mounted secret file or the collector's
secret manager and bind access to a trusted monitoring network. For Prometheus
3.x, the relevant configuration shape is:

```yaml
scrape_configs:
  - job_name: sentinel
    scheme: https
    metrics_path: /metrics
    scrape_interval: 15s
    scrape_timeout: 10s
    static_configs:
      - targets: [sentinel-api.example.com]
    http_headers:
      X-API-Key:
        files:
          - /run/secrets/sentinel_api_key
```

The target hostname and secret path above are examples, not credentials. Keep
`/metrics` authenticated; do not expose it publicly. Verify the
collector's secret-file support and access controls before deployment. This
documentation does not configure a managed monitoring service or change the
current deployment.

### Request IDs and Logs

The request-ID middleware accepts a valid `X-Request-ID` or generates one,
returns it in the response header, and includes it in structured JSON request
logs. Request logs include method, path, status, and duration; the path can
contain route identifiers, so protect log access. Unexpected-error logs include
the exception type and request correlation data without returning exception
details to API clients.
