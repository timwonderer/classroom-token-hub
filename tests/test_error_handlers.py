"""Regression coverage for the styled error handlers registered in wsgi.py.

429 was the one HTTP status Flask-Limiter can raise with no styled handler
registered at all (400/401/403/404/500/503 already had one) -- a rate-limited
user saw Flask-Limiter's bare default page instead of the branded error
pages every other status gets.
"""

import wsgi  # noqa: F401 -- registers the error handlers on import


def test_rate_limited_request_renders_the_styled_429_page(client, app):
    """A route that actually trips Flask-Limiter must render error_429.html,
    not Flask-Limiter's bare default response.
    """
    app.config["RATELIMIT_ENABLED"] = True
    try:
        response = None
        for _ in range(6):
            response = client.get("/admin/recover")
        assert response.status_code == 429
        html = response.data.decode()
        assert "429" in html
        assert "Too Many Requests" in html
        assert "Too many attempts" in html
        assert "5 per 1 hour" in html
    finally:
        app.config["RATELIMIT_ENABLED"] = False
