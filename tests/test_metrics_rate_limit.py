"""The local Prometheus scrape endpoint is not throttled by the default limits.

Live host 2026-09-25: Prometheus scraped /metrics every 15 s against the
default "500 per day" limit, so most scrapes returned 429 and each logged a
warning. Only a local scraper can reach the endpoint, so it is exempt.
"""

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
