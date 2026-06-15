def test_v1_sunset_redirects_all_non_public_routes(client, monkeypatch):
    monkeypatch.setenv("V1_SUNSET_MODE", "true")
    monkeypatch.setenv("V1_SUNSET_TEST_NOW_UTC", "2026-07-01T07:00:00Z")

    response = client.get("/admin/login", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"] == "https://classroomtokenhub.com/v2transition.html"


def test_v1_sunset_allows_transition_page(client, monkeypatch):
    monkeypatch.setenv("V1_SUNSET_MODE", "true")
    monkeypatch.setenv("V1_SUNSET_TEST_NOW_UTC", "2026-07-01T07:00:00Z")

    response = client.get("/v2transition.html")

    assert response.status_code == 200
    assert "Learn more" in response.get_data(as_text=True)


def test_v1_sunset_allows_learn_more_page(client, monkeypatch):
    monkeypatch.setenv("V1_SUNSET_MODE", "true")
    monkeypatch.setenv("V1_SUNSET_TEST_NOW_UTC", "2026-07-01T07:00:00Z")

    response = client.get("/learnmore.html")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'data-sunset-label="Back to Transition Page"' in body
    assert "Back to Home" in body


def test_v1_sunset_allows_required_transition_assets(client, monkeypatch):
    monkeypatch.setenv("V1_SUNSET_MODE", "true")
    monkeypatch.setenv("V1_SUNSET_TEST_NOW_UTC", "2026-07-01T07:00:00Z")

    style_response = client.get("/style.css")
    tokens_response = client.get("/static/css/tokens.css")

    assert style_response.status_code == 200
    assert "landing-hero" in style_response.get_data(as_text=True)
    assert tokens_response.status_code == 200
    assert "--primary" in tokens_response.get_data(as_text=True)


def test_v1_sunset_blocks_health_endpoint(client, monkeypatch):
    monkeypatch.setenv("V1_SUNSET_MODE", "true")
    monkeypatch.setenv("V1_SUNSET_TEST_NOW_UTC", "2026-07-01T07:00:00Z")

    response = client.get("/health", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"] == "https://classroomtokenhub.com/v2transition.html"


def test_v1_sunset_waits_until_start_time(client, monkeypatch):
    monkeypatch.setenv("V1_SUNSET_MODE", "true")
    monkeypatch.setenv("V1_SUNSET_TEST_NOW_UTC", "2026-07-01T06:59:59Z")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "ok"
