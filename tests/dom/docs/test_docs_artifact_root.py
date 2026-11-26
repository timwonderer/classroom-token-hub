"""User guides can be served from a separately published documentation artifact (SOP-DEP-003).

With ``CTH_USER_GUIDES_DIR`` unset, the checkout serves everything as before. With it set, only
``user-guides/`` (pages and search) comes from the artifact; nothing else under ``docs/`` moves,
containment still holds, and artifact HTML is sanitized exactly like checkout HTML.
"""
from pathlib import Path

import pytest

from app.routes import docs as docs_routes

GUIDE = """---
title: Artifact Guide
description: Served from the published documentation artifact.
---

# Artifact Guide

Only the artifact says zephyrquokka.

<script>alert('x')</script>
"""


@pytest.fixture
def artifact(tmp_path, monkeypatch):
    """A published artifact's ``docs`` directory with one guide, wired in via the variable."""
    root = tmp_path / "releases" / ("a" * 40) / "docs"
    (root / "user-guides").mkdir(parents=True)
    (root / "user-guides" / "artifact-guide.md").write_text(GUIDE, encoding="utf-8")
    current = tmp_path / "current"
    current.symlink_to(root.parent)  # served through the switchable symlink, as on the droplet
    monkeypatch.setenv(docs_routes.USER_GUIDES_ROOT_ENV, str(current / "docs"))
    return root


def test_unset_variable_keeps_the_checkout(monkeypatch):
    monkeypatch.delenv(docs_routes.USER_GUIDES_ROOT_ENV, raising=False)
    assert docs_routes.docs_root_for("user-guides/teacher_manual") == docs_routes.DOCS_ROOT
    assert docs_routes.user_guides_docs_root() == docs_routes.DOCS_ROOT


def test_only_user_guides_leave_the_checkout(artifact):
    assert docs_routes.docs_root_for("user-guides/artifact-guide") != docs_routes.DOCS_ROOT
    for other in ("SPEC/x", "user-guidesX/y", "DOMAIN", ""):
        assert docs_routes.docs_root_for(other) == docs_routes.DOCS_ROOT, other


def test_guide_page_is_served_from_the_artifact_and_sanitized(client, artifact):
    response = client.get("/docs/user-guides/artifact-guide")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "zephyrquokka" in body
    assert "<script>alert" not in body


def test_checkout_guides_are_not_served_while_the_artifact_is_active(client, artifact):
    """A guide only the checkout has must not leak through: the artifact is the whole help centre."""
    assert (docs_routes.DOCS_ROOT / "user-guides" / "teacher_manual.md").is_file()
    assert client.get("/docs/user-guides/teacher_manual").status_code == 404


def test_search_reads_the_artifact(client, artifact):
    response = client.get("/docs/search?q=zephyrquokka")
    assert response.status_code == 200
    assert "Artifact Guide" in response.get_data(as_text=True)


def test_a_link_inside_the_artifact_cannot_escape_it(client, artifact, tmp_path):
    secret = tmp_path / "outside.md"
    secret.write_text("# Outside\n\nshould never render\n", encoding="utf-8")
    (artifact / "user-guides" / "escape.md").symlink_to(secret)
    assert client.get("/docs/user-guides/escape").status_code == 404
    response = client.get("/docs/search?q=should+never+render")
    assert "Outside" not in response.get_data(as_text=True)


def test_a_missing_artifact_fails_closed(client, monkeypatch, tmp_path):
    monkeypatch.setenv(docs_routes.USER_GUIDES_ROOT_ENV, str(tmp_path / "absent"))
    assert client.get("/docs/user-guides/teacher_manual").status_code in (404, 500)
