"""Operator notice on the student and teacher login pages (app/utils/login_notice.py)."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.utils.login_notice import parse_login_notice

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
LOGIN_PAGES = ("/student/login", "/admin/login")


def _notice(message="Down for maintenance Saturday 8-10 PM.", expires_at="2026-10-04T05:00:00Z"):
    return json.dumps({"message": message, "expires_at": expires_at})


def test_login_notice_parse_returns_message_before_expiry():
    assert parse_login_notice(_notice(), now=NOW) == "Down for maintenance Saturday 8-10 PM."


def test_login_notice_parse_hides_at_and_after_expiry():
    assert parse_login_notice(_notice(expires_at="2026-10-03T12:00:00Z"), now=NOW) is None
    assert parse_login_notice(_notice(expires_at="2026-10-02T12:00:00+00:00"), now=NOW) is None


def test_login_notice_parse_honours_offsets():
    # 05:30 in Los Angeles (PDT, -07:00) is 12:30 UTC, still ahead of NOW.
    assert parse_login_notice(_notice(expires_at="2026-10-03T05:30:00-07:00"), now=NOW)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not json",
        "[]",
        json.dumps({"expires_at": "2026-10-04T05:00:00Z"}),
        _notice(message="   "),
        _notice(message=42),
        json.dumps({"message": "hi"}),
        _notice(expires_at="tomorrow"),
        _notice(expires_at="2026-10-04T05:00:00"),  # naive: refused, not guessed
        '{"message": "\\ud800", "expires_at": "2026-10-04T05:00:00Z"}',  # lone surrogate
    ],
)
def test_login_notice_parse_refuses_malformed_notice(raw):
    assert parse_login_notice(raw, now=NOW) is None


@pytest.mark.parametrize("page", LOGIN_PAGES)
def test_login_notice_shown_on_login_page(client, app, tmp_path, monkeypatch, page):
    path = tmp_path / "login_notice.json"
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    path.write_text(_notice(message="Maintenance <b>tonight</b> 8-10 PM", expires_at=expires))
    monkeypatch.setitem(app.config, "LOGIN_NOTICE_PATH", str(path))

    response = client.get(page)

    assert response.status_code == 200
    assert b'id="loginNotice"' in response.data
    assert b"Scheduled maintenance" in response.data
    # Operator text is escaped, never rendered as markup.
    assert b"Maintenance &lt;b&gt;tonight&lt;/b&gt; 8-10 PM" in response.data


@pytest.mark.parametrize("page", LOGIN_PAGES)
def test_login_notice_hidden_once_expired(client, app, tmp_path, monkeypatch, page):
    path = tmp_path / "login_notice.json"
    expires = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    path.write_text(_notice(expires_at=expires))
    monkeypatch.setitem(app.config, "LOGIN_NOTICE_PATH", str(path))

    response = client.get(page)

    assert response.status_code == 200
    assert b'id="loginNotice"' not in response.data


@pytest.mark.parametrize("page", LOGIN_PAGES)
def test_login_notice_missing_or_broken_file_does_not_break_login(client, app, tmp_path, monkeypatch, page):
    monkeypatch.setitem(app.config, "LOGIN_NOTICE_PATH", str(tmp_path / "absent.json"))
    response = client.get(page)
    assert response.status_code == 200
    assert b'id="loginNotice"' not in response.data

    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    monkeypatch.setitem(app.config, "LOGIN_NOTICE_PATH", str(broken))
    response = client.get(page)
    assert response.status_code == 200
    assert b'id="loginNotice"' not in response.data

    not_utf8 = tmp_path / "not_utf8.json"
    not_utf8.write_bytes(b'{"message": "caf\xe9", "expires_at": "2099-01-01T00:00:00Z"}')
    monkeypatch.setitem(app.config, "LOGIN_NOTICE_PATH", str(not_utf8))
    response = client.get(page)
    assert response.status_code == 200
    assert b'id="loginNotice"' not in response.data
