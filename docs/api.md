# API Operations

## Prometheus Metrics

`GET /metrics` returns Prometheus text exposition format and requires the same
`X-API-Key` header as the protected API routes. The endpoint is included in the
OpenAPI document. Do not expose it to untrusted networks; operational metrics
can reveal traffic volume and route usage. Restrict scraping to a trusted
monitoring network and store the API key as a secret.

The endpoint reports:

- `sentinel_http_requests_total`, grouped by normalized method, route template,
  and status code.
- `sentinel_http_request_duration_seconds`, a histogram with buckets from
  5 ms through 10 seconds, plus the standard `+Inf`, sum, and count series.
- `sentinel_http_requests_in_progress`, a process-wide gauge.
- `sentinel_http_rate_limit_rejections_total`, counting HTTP 429 responses.

Route labels use FastAPI route templates; unmatched paths share the `unmatched`
label. Unknown methods are normalized to `OTHER`. No request IDs, API keys,
incident identifiers, query parameters, request bodies, or exception details
are used as metric labels. Metrics stay in memory, are updated under a
threading lock, and reset when the process restarts. Requests to `/metrics` are
excluded from the request counters, duration histogram, and in-progress gauge
to prevent scrape traffic from biasing application measurements. Each Render
instance therefore exposes only its own observations; aggregate across
instances in the monitoring system.