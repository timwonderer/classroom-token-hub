"""DOM-OPS-001: external admission never replaces application authentication."""

import pytest


@pytest.mark.parametrize("path, expected", [("/", 302), ("/sysadmin/login", 200), ("/health", 200)])
def test_DOM_OPS_001__retired_flag_cannot_block_requests(client, monkeypatch, path, expected):
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    monkeypatch.setenv("MAINTENANCE_MESSAGE", "obsolete gate message")
    response = client.get(path)
    assert response.status_code == expected
    assert b"obsolete gate message" not in response.data


@pytest.mark.parametrize("old_session", [False, True])
def test_DOM_OPS_001__retired_bypass_cannot_authorize_application(client, monkeypatch, old_session):
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    monkeypatch.setenv("MAINTENANCE_SYSADMIN_BYPASS", "true")
    monkeypatch.setenv("MAINTENANCE_BYPASS_TOKEN", "retired-test-token")
    if old_session:
        with client.session_transaction() as session:
            session["maintenance_global_bypass"] = True
    response = client.get("/sysadmin/dashboard?maintenance_bypass=retired-test-token")
    assert response.status_code == 302
    assert "/sysadmin/login" in response.headers["Location"]
    if not old_session:
        with client.session_transaction() as session:
            assert "maintenance_global_bypass" not in session
