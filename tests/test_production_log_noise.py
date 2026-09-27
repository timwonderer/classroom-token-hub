"""Log hygiene found on production after the v2.0.0 release (2026-09-27).

In five hours with no classes, the application log carried 954 feature-settings
warnings from signed-out pages and a Cloudflare-origin warning on every
Prometheus scrape. Each test pairs the silenced case with a near miss that must
still be reported, so a guard that stops detecting anything goes red.
"""

from unittest.mock import patch

import pytest


def _warnings(mock_warning, needle):
    return [c.args[0] for c in mock_warning.call_args_list if needle in str(c.args[0])]


def test_signed_out_page_does_not_warn_about_feature_settings(app):
    client = app.test_client()
    with patch.object(app.logger, "warning") as mock_warning:
        response = client.get("/student/login")
    assert response.status_code == 200
    assert _warnings(mock_warning, "Could not load feature settings") == []


def test_unexpected_feature_settings_failure_still_warns(app):
    """Only an expected context-resolution outcome is quiet. Any other failure
    to load feature settings still falls back and still warns."""
    client = app.test_client()
    with patch(
        "app.routes.student.get_feature_settings_for_student",
        side_effect=RuntimeError("feature table unavailable"),
    ), patch.object(app.logger, "warning") as mock_warning:
        response = client.get("/student/login")
    assert response.status_code == 200
    assert _warnings(mock_warning, "Could not load feature settings") != []


@pytest.fixture
def production_env(app):
    previous = app.config.get("ENV")
    app.config["ENV"] = "production"
    try:
        yield app
    finally:
        app.config["ENV"] = previous


def test_host_local_request_is_not_a_cloudflare_bypass(production_env):
    """A loopback request with no proxy headers never went through nginx --
    the Prometheus scrape, or an operator's curl on the host."""
    client = production_env.test_client()
    with patch("app.utils.ip_handler.is_cloudflare_ip", return_value=False), \
            patch.object(production_env.logger, "warning") as mock_warning:
        client.get("/student/login", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert _warnings(mock_warning, "Request not from Cloudflare IP") == []


def test_proxied_request_from_a_non_cloudflare_peer_still_warns(production_env):
    """Near miss: the same loopback address, but nginx forwarded it from a
    peer that is not a Cloudflare edge. That is the case the check exists for."""
    client = production_env.test_client()
    with patch("app.utils.ip_handler.is_cloudflare_ip", return_value=False), \
            patch.object(production_env.logger, "warning") as mock_warning:
        client.get(
            "/student/login",
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
            headers={"X-CF-Edge-IP": "203.0.113.7"},
        )
    assert _warnings(mock_warning, "Request not from Cloudflare IP") != []
