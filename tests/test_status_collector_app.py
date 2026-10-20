"""The private HTTP entry point runs the existing collector command once."""

from status_service import collector_app


def test_collector_post_runs_command_once(monkeypatch):
    calls = []
    monkeypatch.setattr(collector_app, "main", lambda: calls.append("collected"))

    response = collector_app.app.test_client().post("/collect")

    assert response.status_code == 204
    assert calls == ["collected"]


def test_collector_does_not_run_on_get_or_failed_command(monkeypatch):
    calls = []

    def fail():
        calls.append("attempted")
        raise RuntimeError("Firestore unavailable")

    monkeypatch.setattr(collector_app, "main", fail)
    client = collector_app.app.test_client()

    assert client.get("/collect").status_code == 405
    assert calls == []
    assert client.post("/collect").status_code == 500
    assert calls == ["attempted"]
