"""Sysadmin sign-out is a POST with a CSRF token; a GET signs nobody out.

``GET /sysadmin/logout`` used to pop the session's principal for whoever held
it. Any GET can be produced without the user's intent: a link or image on
another site, a browser prefetch, a crawler following the landing page. It is
the same GET-time session mutation #1446 removed from ``GET /sysadmin/login``
(tracker §IV-B follow-up to #1469). The route now accepts only POST, so the
global CSRFProtect checks the token before the view runs.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from app import db
from tests.dom.interpretation.helpers import create_sysadmin
from tests.helpers.operation_routes import seed_sysadmin_session

TEMPLATES = Path(__file__).resolve().parents[3] / "templates"
IDENTITY_KEYS = ("user_id", "current_session_nonce", "sysadmin_auth_username")


@pytest.fixture
def csrf_enabled(app, monkeypatch):
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", True)


@pytest.fixture
def sysadmin_session(client, app):
    sysadmin = create_sysadmin("logout_post_only")
    seed_sysadmin_session(client, user_id=sysadmin.id, username="logout_post_only")
    db.session.commit()
    return sysadmin


def _identity(client):
    with client.session_transaction() as sess:
        return {key: sess.get(key) for key in IDENTITY_KEYS}


def _sign_out_form(client):
    page = BeautifulSoup(client.get("/sysadmin/dashboard").data, "html.parser")
    return page.find("form", attrs={"action": "/sysadmin/logout"})


def test_sysadmin_logout_get_is_refused_and_keeps_the_session(client, sysadmin_session):
    before = _identity(client)
    assert before["user_id"] == sysadmin_session.id

    response = client.get("/sysadmin/logout")

    assert response.status_code == 405
    assert _identity(client) == before
    assert client.get("/sysadmin/dashboard").status_code == 200


def test_sysadmin_logout_post_without_csrf_token_is_refused(client, sysadmin_session, csrf_enabled):
    before = _identity(client)

    response = client.post("/sysadmin/logout")

    assert response.status_code == 400
    assert _identity(client) == before
    assert client.get("/sysadmin/dashboard").status_code == 200


def test_sysadmin_logout_post_with_a_forged_csrf_token_is_refused(client, sysadmin_session, csrf_enabled):
    before = _identity(client)

    response = client.post("/sysadmin/logout", data={"csrf_token": "forged"})

    assert response.status_code == 400
    assert _identity(client) == before


def test_sysadmin_sidebar_sign_out_posts_with_csrf_and_ends_the_session(client, sysadmin_session, csrf_enabled):
    form = _sign_out_form(client)
    assert form is not None, "the sidebar offers Sign Out as a form"
    assert form["method"].lower() == "post"
    token = form.find("input", attrs={"name": "csrf_token"})
    assert token is not None and token["value"]
    button = form.find("button", attrs={"type": "submit"})
    assert button is not None and "Sign Out" in button.get_text(" ", strip=True)

    response = client.post(form["action"], data={"csrf_token": token["value"]})

    assert response.status_code == 302
    assert response.location.split("?")[0].endswith("/sysadmin/login")
    assert _identity(client)["user_id"] is None
    assert _identity(client)["current_session_nonce"] is None
    # Signed out: the console sends the browser to sign in.
    console = client.get("/sysadmin/dashboard")
    assert console.status_code == 302
    assert "/sysadmin/login" in console.location


def test_sysadmin_sidebar_has_no_get_link_to_logout(client, sysadmin_session):
    page = BeautifulSoup(client.get("/sysadmin/dashboard").data, "html.parser")
    assert page.select('a[href^="/sysadmin/logout"]') == []


# ---------------------------------------------------------- structural guard
#
# SOP-TEST-003 §IX.A: the detector is a pure function over template text, and
# a companion test feeds it near-miss violations to prove it still detects.

_GET_LINK_TO_SYSADMIN_LOGOUT = re.compile(
    r"""href\s*=\s*["'][^"']*(?:url_for\(\s*["']sysadmin\.logout["']|/sysadmin/logout)""",
)


def find_get_links_to_sysadmin_logout(source: str) -> list[str]:
    """Every ``href`` in ``source`` that points at the sysadmin logout."""
    return [match.group(0) for match in _GET_LINK_TO_SYSADMIN_LOGOUT.finditer(source)]


def test_no_template_links_to_sysadmin_logout_by_get():
    offenders = {
        str(path.relative_to(TEMPLATES)): hits
        for path in TEMPLATES.rglob("*.html")
        if (hits := find_get_links_to_sysadmin_logout(path.read_text(encoding="utf-8")))
    }
    assert offenders == {}, "sysadmin sign-out must be a POST form with a CSRF token"


@pytest.mark.parametrize(
    "violation",
    [
        """<a href="{{ url_for('sysadmin.logout') }}" class="sysadmin-nav-signout">Sign Out</a>""",
        """<a class="x" href='{{ url_for("sysadmin.logout") }}'>Sign Out</a>""",
        """<a href="{{url_for( 'sysadmin.logout' )}}">Sign Out</a>""",
        """<a href="/sysadmin/logout">Sign Out</a>""",
        """<a href="/sysadmin/logout?next=/">Sign Out</a>""",
    ],
)
def test_guard_mutation_proof_detects_a_get_link(violation):
    assert find_get_links_to_sysadmin_logout(violation)


@pytest.mark.parametrize(
    "allowed",
    [
        """<form method="post" action="{{ url_for('sysadmin.logout') }}"><button>Sign Out</button></form>""",
        """<a href="{{ url_for('admin.logout') }}">Sign Out</a>""",
        """<a href="{{ url_for('sysadmin.login') }}">Sign in</a>""",
    ],
)
def test_guard_allows_a_post_form_and_other_logouts(allowed):
    assert find_get_links_to_sysadmin_logout(allowed) == []
