"""Forwarding headers choose a client address only behind our own proxy (audit S7).

``CF-Connecting-IP`` and ``X-Forwarded-For`` are request headers. The rate
limiter and the audit/Turnstile address both read them, so a connection that
reaches the application without passing through the reverse proxy could rotate
them to reset every per-address limit. The DigitalOcean firewall and nginx are
meant to make that unreachable; this holds the application side of the
guarantee: only a loopback (or ``TRUSTED_PROXY_CIDRS``) peer vouches for them.
"""

from __future__ import annotations

import pytest

from app.extensions import get_real_ip_for_limiter, limiter
from app.utils.ip_handler import get_real_ip, peer_is_trusted_proxy

OUTSIDER = {"REMOTE_ADDR": "198.51.100.20"}
PROXY = {"REMOTE_ADDR": "127.0.0.1"}


def _headers(address="203.0.113.50"):
    return {"CF-Connecting-IP": address, "X-Forwarded-For": f"{address}, 10.0.0.1"}


def test_a_loopback_peer_is_the_trusted_proxy(app):
    with app.test_request_context("/", environ_base=PROXY):
        assert peer_is_trusted_proxy()
    with app.test_request_context("/", environ_base={"REMOTE_ADDR": "::1"}):
        assert peer_is_trusted_proxy()


def test_any_other_peer_is_not_a_trusted_proxy(app):
    for peer in ("198.51.100.20", "10.1.2.3", "172.17.0.2", None):
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": peer}):
            assert not peer_is_trusted_proxy(), peer


def test_behind_the_proxy_the_forwarded_address_is_still_the_key(app):
    """Control: production topology is unchanged, so the tests below fail only
    because of the peer check."""
    with app.test_request_context("/", environ_base=PROXY, headers=_headers()):
        assert get_real_ip_for_limiter() == "203.0.113.50"
        assert get_real_ip() == "203.0.113.50"
    with app.test_request_context(
        "/", environ_base=PROXY, headers={"X-Forwarded-For": "203.0.113.60, 10.0.0.1"}
    ):
        assert get_real_ip_for_limiter() == "203.0.113.60"


def test_an_outsider_cannot_choose_its_limiter_key_or_audit_address(app):
    with app.test_request_context("/", environ_base=OUTSIDER, headers=_headers()):
        assert get_real_ip_for_limiter() == "198.51.100.20"
        assert get_real_ip() == "198.51.100.20"


def test_an_outsider_with_no_address_still_gets_a_nonempty_key(app):
    """An empty key makes Flask-Limiter skip the limit, which would fail open."""
    with app.test_request_context("/", environ_base={"REMOTE_ADDR": None}, headers=_headers()):
        assert get_real_ip_for_limiter() == "unknown"


def test_trusted_proxy_cidrs_extends_the_trusted_peers(app, monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "172.17.0.0/16, not-a-cidr")
    with app.test_request_context(
        "/", environ_base={"REMOTE_ADDR": "172.17.0.2"}, headers=_headers()
    ):
        assert get_real_ip_for_limiter() == "203.0.113.50"
    with app.test_request_context("/", environ_base=OUTSIDER, headers=_headers()):
        assert get_real_ip_for_limiter() == "198.51.100.20"


@pytest.fixture
def limiter_on(app):
    was_enabled = limiter.enabled
    limiter.enabled = True
    limiter.reset()
    try:
        yield
    finally:
        limiter.reset()
        limiter.enabled = was_enabled


def _statuses(client, peer, count):
    """`/admin/resume-credentials` allows 10 per hour per address."""
    return [
        client.get(
            "/admin/resume-credentials",
            environ_base={"REMOTE_ADDR": peer},
            headers={"CF-Connecting-IP": f"203.0.113.{index}"},
        ).status_code
        for index in range(count)
    ]


def test_rotating_the_forwarded_address_does_not_reset_an_outsiders_limit(client, limiter_on):
    statuses = _statuses(client, "198.51.100.20", 12)
    assert statuses[:10] == [200] * 10
    assert statuses[10:] == [429, 429]


def test_behind_the_proxy_each_forwarded_client_has_its_own_budget(client, limiter_on):
    """Control: the same rotation through the proxy is twelve different clients,
    which is the O1 behaviour the limiter is built around."""
    assert _statuses(client, "127.0.0.1", 12) == [200] * 12


def test_cloudflare_ranges_are_cached_for_24_hours(app, monkeypatch):
    """The fetched ranges are reused until exactly 24 elapsed hours, then refetched."""
    import urllib.error
    from datetime import datetime, timedelta, timezone

    from app.utils import ip_handler

    fetched_at = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    cached = (["192.0.2.0/24"], ["2001:db8::/32"])
    monkeypatch.setattr(ip_handler, "_cloudflare_ips_cache", cached)
    monkeypatch.setattr(ip_handler, "_cloudflare_ips_cache_time", fetched_at)

    def _offline(*_args, **_kwargs):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(ip_handler.urllib.request, "urlopen", _offline)
    pin = "app.utils.canonical_temporal_resolver.utc_now"
    with app.app_context():
        monkeypatch.setattr(pin, lambda: fetched_at + timedelta(hours=24) - timedelta(seconds=1))
        assert ip_handler.get_cloudflare_ips() == cached
        monkeypatch.setattr(pin, lambda: fetched_at + timedelta(hours=24))
        assert ip_handler.get_cloudflare_ips() == (
            ip_handler.CLOUDFLARE_IPV4_FALLBACK, ip_handler.CLOUDFLARE_IPV6_FALLBACK,
        )
