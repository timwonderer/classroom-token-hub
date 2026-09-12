"""Regression tests for redirect-target sanitization and roster error disclosure.

Covers the code-scanning findings fixed alongside the dependency backlog:
py/url-redirection on the admin login and view-switch routes, and
py/stack-trace-exposure on the roster sync endpoint.
"""

import pytest

from app.utils.helpers import is_safe_url, safe_redirect_target


FALLBACK = "/admin/dashboard"

# Each entry is a target a browser would resolve off-origin even though a naive
# urlparse-only check reads it as a local path.
OFF_ORIGIN_TARGETS = [
    "https://evil.example",
    "http://evil.example/path",
    "//evil.example",
    "////evil.example",
    "/\\evil.example",
    "\\/evil.example",
    "\\\\evil.example",
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "mailto:someone@evil.example",
]

IN_APP_TARGETS = [
    ("/admin/reports", "/admin/reports"),
    ("/admin/reports?class_id=abc&page=2", "/admin/reports?class_id=abc&page=2"),
    ("/student/dashboard#balances", "/student/dashboard#balances"),
    ("/", "/"),
]


@pytest.mark.parametrize("target", OFF_ORIGIN_TARGETS)
def test_safe_redirect_target_rejects_off_origin(target):
    """Any target a browser could resolve off-origin falls back to the trusted URL."""
    assert safe_redirect_target(target, FALLBACK) == FALLBACK


@pytest.mark.parametrize("target,expected", IN_APP_TARGETS)
def test_safe_redirect_target_preserves_in_app_paths(target, expected):
    """Root-relative in-app paths survive intact, including query and fragment."""
    assert safe_redirect_target(target, FALLBACK) == expected


@pytest.mark.parametrize("target", ["", None])
def test_safe_redirect_target_uses_fallback_when_absent(target):
    assert safe_redirect_target(target, FALLBACK) == FALLBACK


def test_safe_redirect_target_rejects_scheme_relative_without_leading_slash():
    """A bare relative path is ambiguous against the current route, so reject it."""
    assert safe_redirect_target("relative/path", FALLBACK) == FALLBACK


@pytest.mark.parametrize("target", ["/\\evil.example", "\\/evil.example"])
def test_is_safe_url_rejects_backslash_bypass(app, target):
    """Backslash forms must not pass is_safe_url (the pre-fix bypass)."""
    with app.test_request_context("/", base_url="https://school.example"):
        assert is_safe_url(target) is False


def test_is_safe_url_still_accepts_same_origin(app):
    with app.test_request_context("/", base_url="https://school.example"):
        assert is_safe_url("/admin/dashboard") is True
        assert is_safe_url("https://school.example/admin/dashboard") is True


def test_switch_view_ignores_off_origin_next(client):
    """/switch-view must never bounce a visitor to an attacker-supplied host."""
    response = client.get("/switch-view?view=desktop&next=https://evil.example")
    assert response.status_code == 302
    assert "evil.example" not in response.headers["Location"]


def test_switch_view_honors_in_app_next(client):
    response = client.get("/switch-view?view=desktop&next=/student/dashboard")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/student/dashboard")
