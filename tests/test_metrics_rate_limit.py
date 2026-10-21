"""The local Prometheus scrape endpoint is not throttled by the default limits.

Live host 2026-09-25: Prometheus scraped /metrics every 15 s against the
default "500 per day" limit, so most scrapes returned 429 and each logged a
warning. Only a local scraper can reach the endpoint, so it is exempt.

Live host 2026-10-20: the status collector moved from a Cloud Run Job (a new
egress address each run) to a long-lived service (one address). Its once-a-
minute /health/status probe spent "500 per day" by 15:10Z and every later probe
returned 429, so the public status page reported an outage. The health probes
are exempt for the same reason.
"""
import pytest

from app.extensions import limiter


def test_metrics_is_exempt_from_default_rate_limits(app, client):
    was_enabled = limiter.enabled
    limiter.enabled = True
    try:
        with app.app_context():
            limiter.reset()
        statuses = {
            client.get("/metrics", environ_base={"REMOTE_ADDR": "127.0.0.1"}).status_code
            for _ in range(201)  # one past the "200 per hour" default
        }
    finally:
        limiter.enabled = was_enabled
    assert statuses == {200}


@pytest.mark.parametrize("path", ["/health", "/health/status"])
def test_health_probes_are_exempt_from_default_rate_limits(app, client, path):
    was_enabled = limiter.enabled
    limiter.enabled = True
    try:
        with app.app_context():
            limiter.reset()
        statuses = {
            client.get(path, environ_base={"REMOTE_ADDR": "2600:1900:0:2e01::e00"}).status_code
            for _ in range(201)  # one past the "200 per hour" default
        }
    finally:
        limiter.enabled = was_enabled
    assert statuses == {200}
