"""Teacher session failures use teacher wording and never flash from background calls.

Regression: signing out while the getting-started widget's background
``/admin/onboarding/status`` request was in flight made ``admin_required`` flash
"System admin session is invalid" into the session, which then appeared on the
teacher login page.
"""
from tests.helpers.classroom_initializer import initialize_as_teacher

BACKGROUND = {"Sec-Fetch-Mode": "cors"}
NAVIGATION = {"Sec-Fetch-Mode": "navigate"}


def _flashes(client):
    with client.session_transaction() as session:
        return [message for _category, message in session.get("_flashes", [])]


def test_background_call_after_sign_out_leaves_no_message_on_login(client, app):
    initialize_as_teacher("chemistry_p1", client, app)
    client.get("/admin/logout", headers=NAVIGATION)
    with client.session_transaction() as session:
        session.pop("_flashes", None)  # the ordinary "Logged out." message

    response = client.get("/admin/onboarding/status", headers=BACKGROUND)

    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"
    assert _flashes(client) == []
    login = client.get("/admin/login", headers=NAVIGATION).get_data(as_text=True)
    assert "System admin" not in login and "session has ended" not in login


def test_page_navigation_without_session_redirects_with_teacher_wording(client, app):
    response = client.get("/admin/students", headers=NAVIGATION)
    assert response.status_code == 302 and "/admin/login" in response.location
    assert _flashes(client) == ["Your session has ended. Please log in again."]


def test_json_request_without_session_gets_401_without_flash(client, app):
    response = client.post("/admin/student/unclaim", json={})
    assert response.status_code == 401
    assert _flashes(client) == []
