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

from app.utils.helpers import USER_GUIDES_DIR, docs_url_for

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


def test_technical_deep_links_keep_their_path(app, monkeypatch):
    """An unmapped developer path forwards to the same path on the docs site.

    The docs site publishes docs/ at its repository-relative paths, so there is
    nothing to translate. Before this, an unmapped path collapsed to the site
    root and the reader lost the document they asked for.
    """
    monkeypatch.setitem(app.config, "EXTERNAL_DOCS_BASE_URL", EXTERNAL)
    with app.test_request_context("/"):
        assert docs_url_for(TECHNICAL) == f"{EXTERNAL}/{TECHNICAL}"


def test_technical_deep_link_redirect_keeps_its_path(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "EXTERNAL_DOCS_BASE_URL", EXTERNAL)

    response = client.get(f"/docs/{TECHNICAL}", follow_redirects=False)

    assert response.headers["Location"] == f"{EXTERNAL}/{TECHNICAL}"


def test_a_renamed_path_still_honours_the_route_map(app, monkeypatch):
    """route-map.json carries the exceptions: paths that changed on the way over."""
    monkeypatch.setitem(app.config, "EXTERNAL_DOCS_BASE_URL", EXTERNAL)
    renamed = "ARCHITECTURE/ARC-CORE-000_Architecture_Foundation"
    with app.test_request_context("/"):
        assert docs_url_for(renamed) == (
            f"{EXTERNAL}/INVARIANT/ARCHITECTURE/INV-ARC-000_EXECUTION_MODEL"
        )


def test_the_route_map_never_forwards_the_help_centre(app):
    """Listing user-guides would hand the app's own tree to the docs site."""
    from app.utils.helpers import EXTERNAL_DOCS_ROUTE_MAP, is_user_guide_doc_path

    assert not [
        path for path in EXTERNAL_DOCS_ROUTE_MAP if is_user_guide_doc_path(path)
    ]


def _docs_site_config_source():
    from pathlib import Path

    return (
        Path(__file__).resolve().parents[3] / "docs-site" / "docusaurus.config.js"
    ).read_text(encoding="utf-8")


def excluded_trees(config_source):
    """Directories the Docusaurus docs plugin is told not to publish.

    Pure over the config text so the detector itself can be tested against a
    synthetic violation rather than only against a compliant repository.
    """
    import re

    match = re.search(r"exclude:\s*\[(.*?)\]", config_source, re.DOTALL)
    if not match:
        return frozenset()
    return frozenset(
        entry.removesuffix("/**")
        for entry in re.findall(r'"([^"]+)"', match.group(1))
    )


def test_excluded_trees_reports_a_site_that_would_publish_the_help_centre():
    """Mutation proof: the detector must fail a config that drops the exclusion.

    The near miss a future edit would really produce is an exclude list that
    still excludes the archive but no longer excludes user-guides.
    """
    mutated = '''
      docs: {
        path: "../docs",
        exclude: ["archive/**", "assets/**", "README.md"],
      }
    '''

    assert USER_GUIDES_DIR not in excluded_trees(mutated)
    assert "archive" in excluded_trees(mutated)


def test_the_docs_site_excludes_every_tree_the_app_serves():
    """The generator's exclude list and the app's boundary must agree."""
    excluded = excluded_trees(_docs_site_config_source())

    assert USER_GUIDES_DIR in excluded
    assert "archive" in excluded


def test_the_docs_site_publishes_the_developer_tree():
    """The site reads the repository tree; it never keeps a copy of its own."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]

    assert 'path: "../docs"' in _docs_site_config_source()
    assert not (root / "docs-site" / "docs").exists()

    published = {"INVARIANT", "DOMAIN", "FEATURE-EXECUTION", "SPEC", "MAP"}
    assert not published & excluded_trees(_docs_site_config_source())
