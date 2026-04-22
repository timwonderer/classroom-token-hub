from app.utils.helpers import docs_url_for


def test_docs_url_for_prefers_local_routes_for_authenticated_sessions(app):
    with app.test_request_context("/admin/"):
        from flask import session

        session["admin_id"] = 123
        app.config["EXTERNAL_DOCS_BASE_URL"] = "https://docs.classroomtokenhub.com"

        assert docs_url_for("user-guides/diagnostics/teacher") == "/docs/user-guides/diagnostics/teacher"


def test_docs_url_for_prefers_external_routes_for_public_sessions(app):
    with app.test_request_context("/"):
        app.config["EXTERNAL_DOCS_BASE_URL"] = "https://docs.classroomtokenhub.com"

        assert docs_url_for("user-guides/diagnostics/teacher") == (
            "https://docs.classroomtokenhub.com/user-guides/diagnostics/teacher"
        )


def test_public_docs_index_redirects_when_external_site_is_configured(client, app):
    app.config["EXTERNAL_DOCS_BASE_URL"] = "https://docs.classroomtokenhub.com"

    response = client.get("/docs/", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"] == "https://docs.classroomtokenhub.com"


def test_authenticated_docs_stay_in_app_when_external_site_is_configured(client, app):
    app.config["EXTERNAL_DOCS_BASE_URL"] = "https://docs.classroomtokenhub.com"

    with client.session_transaction() as sess:
        sess["admin_id"] = 1
        sess["is_admin"] = True

    response = client.get("/docs/user-guides/teacher_manual", follow_redirects=False)

    assert response.status_code == 200


def test_unmapped_public_docs_stay_in_flask_when_external_site_is_configured(client, app):
    app.config["EXTERNAL_DOCS_BASE_URL"] = "https://docs.classroomtokenhub.com"

    response = client.get("/docs/user-guides/teacher_manual", follow_redirects=False)

    assert response.status_code == 200


def test_public_search_stays_in_flask_until_external_search_is_migrated(client, app):
    app.config["EXTERNAL_DOCS_BASE_URL"] = "https://docs.classroomtokenhub.com"

    response = client.get("/docs/search?q=teacher", follow_redirects=False)

    assert response.status_code == 200
