"""Private, bounded Prometheus metrics for proven application boundaries."""

from __future__ import annotations

import logging

# SPEC-OPS-003 §VII: telemetry failure MUST NOT change the result, transaction
# boundary, authorization, rollback behavior, or user-visible business outcome.
# A module-scope import is the harshest way to violate that — `app/__init__.py`
# imports this during `create_app()`, so an absent package takes down the entire
# application rather than the observability surface alone. `prometheus-client`
# is pinned in `requirements.txt` and is expected to be present; this guard
# governs what happens when it is not, and nothing else.
try:
    from prometheus_client import Counter, Histogram, generate_latest

    TELEMETRY_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only on an incomplete install
    TELEMETRY_AVAILABLE = False

logger = logging.getLogger(__name__)

if TELEMETRY_AVAILABLE:
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
else:
    HTTP_REQUESTS = None
    HTTP_DURATION = None
    logger.warning(
        "prometheus_client is unavailable; application telemetry is disabled. "
        "The /metrics endpoint will report no series. Install the pinned "
        "requirements to restore observability."
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
    if not TELEMETRY_AVAILABLE:
        return
    capability = CAPABILITY_BY_ENDPOINT.get(endpoint or "")
    if capability is None:
        return
    outcome = "SUCCESS" if 200 <= status_code < 400 else "SYSTEM_FAILURE"
    # Recording runs in an after_request hook, so an exception here would
    # surface to the client as a failed request. SPEC-OPS-003 §VII forbids
    # telemetry altering a user-visible outcome; the observation is dropped.
    try:
        HTTP_REQUESTS.labels(capability, method, outcome).inc()
        HTTP_DURATION.labels(capability, method).observe(max(0.0, elapsed_seconds))
    except Exception:
        logger.exception("Dropped a telemetry observation for capability %s", capability)


def metrics_payload() -> bytes:
    """Return the bounded Prometheus exposition payload.

    Empty when telemetry is unavailable: a scrape that returns no series is
    honest about the absence, where a 500 would misreport it as an application
    fault.
    """
    if not TELEMETRY_AVAILABLE:
        return b""
    return generate_latest()


__all__ = [
    "CAPABILITY_BY_ENDPOINT",
    "TELEMETRY_AVAILABLE",
    "metrics_payload",
    "record_request",
]
