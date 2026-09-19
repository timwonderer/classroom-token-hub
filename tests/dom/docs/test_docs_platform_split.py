"""The application serves the help centre; the technical site serves the rest.

`docs/user-guides` is the in-app help centre for teachers and students, rendered
by the Flask docs blueprint. Every other directory under `docs/` is
developer-facing and is published by the separate technical site. The split is
about who owns the rendering, not about access: the repository is public.

Regression this pins: the boundary used to be read off
`docs-site/route-map.json`, which lists `user-guides` as migrated, and
`get_external_docs_target(None)` returns `""` rather than `None` for the index.
Together those meant that configuring `EXTERNAL_DOCS_BASE_URL` redirected the
working in-app help centre — and its index — off the application entirely.
"""

from app.utils.helpers import docs_url_for

EXTERNAL = "https://docs.classroomtokenhub.com"
GUIDE = "user-guides/features/teacher/classroom/student-issues"
TECHNICAL = "DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY"


def test_help_centre_links_stay_in_the_app_even_with_an_external_site(app, monkeypatch):
    monkeypatch.setitem(app.config, "EXTERNAL_DOCS_BASE_URL", EXTERNAL)
    with app.test_request_context("/"):
        assert docs_url_for(GUIDE) == f"/docs/{GUIDE}"


def test_technical_links_point_at_the_external_site(app, monkeypatch):
    monkeypatch.setitem(app.config, "EXTERNAL_DOCS_BASE_URL", EXTERNAL)
    with app.test_request_context("/"):
        assert docs_url_for(TECHNICAL).startswith(EXTERNAL)


def test_help_centre_index_is_served_by_the_app(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "EXTERNAL_DOCS_BASE_URL", EXTERNAL)

    response = client.get("/docs/", follow_redirects=False)

    assert response.status_code == 200


def test_help_centre_page_is_served_by_the_app(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "EXTERNAL_DOCS_BASE_URL", EXTERNAL)

    response = client.get(f"/docs/{GUIDE}", follow_redirects=False)

    assert response.status_code == 200


def test_technical_doc_redirects_to_the_external_site(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "EXTERNAL_DOCS_BASE_URL", EXTERNAL)

    response = client.get(f"/docs/{TECHNICAL}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].startswith(EXTERNAL)


def test_technical_doc_is_absent_when_no_external_site_is_configured(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "EXTERNAL_DOCS_BASE_URL", "")

    response = client.get(f"/docs/{TECHNICAL}", follow_redirects=False)

    assert response.status_code == 404


def test_an_operator_session_does_not_reopen_the_technical_tree(client, app, monkeypatch):
    """The audience toggle is gone: one tree, one renderer, one navigation."""
    monkeypatch.setitem(app.config, "EXTERNAL_DOCS_BASE_URL", EXTERNAL)
    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["sysadmin_id"] = 1

    response = client.get(f"/docs/{TECHNICAL}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].startswith(EXTERNAL)


def test_search_indexes_only_the_help_centre(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "EXTERNAL_DOCS_BASE_URL", EXTERNAL)

    response = client.get("/docs/search?q=class", follow_redirects=False)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "DOM-CORE-001" not in body
    assert "STANDARD_OPERATING_PROCEDURES" not in body
