"""Regression coverage for the styled error handlers registered in wsgi.py.

429 was the one HTTP status Flask-Limiter can raise with no styled handler
registered at all (400/401/403/404/500/503 already had one) -- a rate-limited
user saw Flask-Limiter's bare default page instead of the branded error
pages every other status gets.
"""

import re

import wsgi  # noqa: F401 -- registers the error handlers on import


def test_rate_limited_request_renders_the_styled_429_page(client, app):
    """A route that actually trips Flask-Limiter must render error_429.html,
    not Flask-Limiter's bare default response.
    """
    app.config["RATELIMIT_ENABLED"] = True
    try:
        response = None
        for _ in range(6):
            response = client.post("/admin/recover", data={})
        assert response.status_code == 429
        html = response.data.decode()
        assert "429" in html
        assert "Too Many Requests" in html
        assert "Too many attempts" in html
        assert "5 per 1 hour" in html
    finally:
        app.config["RATELIMIT_ENABLED"] = False


def test_recover_page_loads_are_not_rate_limited(client, app):
    """GET only renders the form -- it must not share POST's guess-attempt
    bucket, or a student reloading the page while their teacher fills it out
    locks out the actual recovery attempt for no security benefit.
    """
    app.config["RATELIMIT_ENABLED"] = True
    try:
        for _ in range(10):
            response = client.get("/admin/recover")
            assert response.status_code == 200
    finally:
        app.config["RATELIMIT_ENABLED"] = False


def test_teapot_route_answers_418_im_a_teapot_with_the_styled_page(client):
    """RFC 2324 §2.3.2: the status line is exactly `418 I'm a teapot`, and the
    body is the styled error page, not Werkzeug's bare default.
    """
    response = client.get("/teapot")
    assert response.status == "418 I'm a teapot"
    html = response.data.decode()
    assert '<h1 id="error-heading">418</h1>' in html
    assert "This server is a teapot" in html
    assert "rfc2324#section-2.3.2" in html


def test_404_page_header_icon_links_to_the_teapot(client):
    response = client.get("/no-such-page-anywhere")
    assert response.status_code == 404
    assert 'href="/teapot"' in response.data.decode()


def test_teapot_page_headings_never_skip_a_level(client):
    """INV-ARC-020 §VI.2: each heading is at most one level below the one before."""
    levels = [int(n) for n in re.findall(r"<h([1-6])\b", client.get("/teapot").data.decode())]
    assert levels[0] == 1
    assert all(b <= a + 1 for a, b in zip(levels, levels[1:])), levels
