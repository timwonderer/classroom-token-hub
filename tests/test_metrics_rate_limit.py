"""The local Prometheus scrape endpoint is not throttled by the default limits.

Live host 2026-09-25: Prometheus scraped /metrics every 15 s against the
default "500 per day" limit, so most scrapes returned 429 and each logged a
warning. Only a local scraper can reach the endpoint, so it is exempt.

Live host 2026-10-20: the status collector moved from a Cloud Run Job (a new
egress address each run) to a long-lived service (one address). Its once-a-
minute /health/status probe spent "500 per day" by 15:10Z and every later probe
returned 429, so the public status page reported an outage. The health probes
now carry their own "30 per minute" per visitor instead of the daily defaults:
the collector stays far inside it, and nobody can poll the database check
without limit (#1661 follow-up, 2026-10-23).

Live host 2026-10-23 (#1661): /metrics answered the internet, because nginx
proxies over loopback and the guard read only ``remote_addr``.
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
def test_health_probes_are_limited_per_visitor_not_by_the_daily_defaults(app, client, path):
    was_enabled = limiter.enabled
    limiter.enabled = True
    try:
        with app.app_context():
            limiter.reset()
        collector = {"REMOTE_ADDR": "2600:1900:0:2e01::e00"}
        statuses = [client.get(path, environ_base=collector).status_code for _ in range(31)]
        endpoint = app.url_map.bind("localhost").match(path)[0]
        applied = {str(limit.limit) for group in limiter.limit_manager.resolve_limits(
            app, endpoint, blueprint="main") for limit in group}
    finally:
        limiter.enabled = was_enabled
    assert statuses == [200] * 30 + [429]
    # The daily defaults the collector exhausted on 2026-10-20 no longer apply.
    assert applied == {"30 per 1 minute"}


@pytest.mark.parametrize("headers", [
    {"X-Real-IP": "203.0.113.9"},
    {"X-Forwarded-For": "203.0.113.9"},
    {"X-CF-Edge-IP": "172.68.1.1"},
    {"CF-Connecting-IP": "203.0.113.9"},
])
def test_metrics_refuses_a_loopback_request_that_came_through_nginx(client, headers):
    response = client.get("/metrics", environ_base={"REMOTE_ADDR": "127.0.0.1"}, headers=headers)
    assert response.status_code == 404


def test_metrics_refuses_a_remote_peer(client):
    assert client.get("/metrics", environ_base={"REMOTE_ADDR": "203.0.113.9"}).status_code == 404
