"""Private, bounded Prometheus metrics for proven application boundaries."""

from __future__ import annotations

from prometheus_client import Counter, Histogram, generate_latest


HTTP_REQUESTS = Counter(
    "cth_http_requests_total",
    "Completed requests at instrumented application boundaries.",
    ("capability", "method", "outcome"),
)
HTTP_DURATION = Histogram(
    "cth_http_request_duration_seconds",
    "Request duration at instrumented application boundaries.",
    ("capability", "method"),
)

# Deliberately small until each additional route contract is reviewed.
CAPABILITY_BY_ENDPOINT = {
    "main.health_check": "public_service_reachability",
}


def record_request(*, endpoint: str | None, method: str, status_code: int, elapsed_seconds: float) -> None:
    """Record only outcomes proven by the current boundary contract.

    Client/business denials are intentionally not inferred from HTTP status.
    The health endpoint has no denial path; other endpoints are left
    uninstrumented until their owning contract supplies the classification.
    """
    capability = CAPABILITY_BY_ENDPOINT.get(endpoint or "")
    if capability is None:
        return
    outcome = "SUCCESS" if 200 <= status_code < 400 else "SYSTEM_FAILURE"
    HTTP_REQUESTS.labels(capability, method, outcome).inc()
    HTTP_DURATION.labels(capability, method).observe(max(0.0, elapsed_seconds))


def metrics_payload() -> bytes:
    """Return the bounded Prometheus exposition payload."""
    return generate_latest()


__all__ = ["CAPABILITY_BY_ENDPOINT", "metrics_payload", "record_request"]
