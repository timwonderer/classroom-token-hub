"""The fixture-render accessibility gate must itself fail when it should.

SOP-TEST-003 §IX.A: a guard that has never been seen failing is not evidence.
These tests feed the harness and the coverage guard synthetic violations, in
the spelling a real regression would take.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest
from jinja2 import ChoiceLoader, DictLoader

from app import app as flask_app
from tests import a11y_fixtures
from tests.a11y_fixtures import FixtureRenderError, RenderState, load_registry, render_state
from tests.helpers.axe_wcag import (
    audit_fixture_states,
    skip_or_fail_without_browser,
    sync_playwright,
    wcag_live_server,  # noqa: F401 -- fixture, used via pytest injection
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"

_SPEC = importlib.util.spec_from_file_location(
    "check_axe_template_coverage", REPO_ROOT / "scripts" / "check_axe_template_coverage.py")
guard = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(guard)

_BAD_CONTRAST = (
    "<!DOCTYPE html><html lang='en'><head><title>t</title></head><body><main>"
    "<h1>Probe</h1><p style='color:#bbb;background:#fff'>Pale grey on white</p></main></body></html>"
)
_GOOD = (
    "<!DOCTYPE html><html lang='en'><head><title>t</title></head><body><main>"
    "<h1>Probe</h1><p style='color:#222;background:#fff'>Dark on white</p></main></body></html>"
)


def _state(template: str, context=lambda: {}, name: str = "default") -> RenderState:
    return RenderState(template=template, state=name, context=context, path="/probe")


@pytest.fixture
def probe_templates(app, monkeypatch):
    """Add throwaway templates to the real Jinja environment for one test."""
    def install(**sources: str) -> None:
        monkeypatch.setattr(
            app.jinja_env, "loader", ChoiceLoader([DictLoader(sources), app.jinja_env.loader])
        )
    return install


def _run_guard(tmp_path, *, changed, routes=(), fixtures=None, exemptions=None, templates=None) -> int:
    tdir = tmp_path / "templates"
    tdir.mkdir(exist_ok=True)
    for name, body in (templates or {}).items():
        (tdir / name).parent.mkdir(parents=True, exist_ok=True)
        (tdir / name).write_text(body, encoding="utf-8")
    (tmp_path / "changed.txt").write_text("\n".join(f"templates/{n}" for n in changed), encoding="utf-8")
    (tmp_path / "routes.json").write_text(json.dumps(sorted(routes)), encoding="utf-8")
    argv = ["--changed", str(tmp_path / "changed.txt"), "--rendered", str(tmp_path / "routes.json"),
            "--templates-dir", str(tdir), "--exemptions", str(tmp_path / "ex.json")]
    if fixtures is not None:
        (tmp_path / "fixtures.json").write_text(json.dumps(sorted(fixtures)), encoding="utf-8")
        argv += ["--fixture-rendered", str(tmp_path / "fixtures.json")]
    (tmp_path / "ex.json").write_text(json.dumps(exemptions or {}), encoding="utf-8")
    return guard.main(argv)


TREE = {
    "layout.html": "<html>{% block c %}{% endblock %}</html>",
    "routed.html": "{% extends 'layout.html' %}",
    "fixtured.html": "{% extends 'layout.html' %}{% include 'part.html' %}",
    "part.html": "<p>part</p>",
    "orphan.html": "<p>nothing renders this</p>",
    "route_only.html": "<p>standalone routed page</p>",
}


# ---- the coverage guard ------------------------------------------------------

def test_1_changed_template_with_a_registered_fixture_passes(tmp_path):
    assert _run_guard(tmp_path, changed=["fixtured.html"], routes=["routed.html"],
                      fixtures=["fixtured.html"], templates=TREE) == 0


def test_2_changed_template_with_neither_route_nor_fixture_fails(tmp_path, capsys):
    assert _run_guard(tmp_path, changed=["orphan.html"], routes=["routed.html"],
                      fixtures=["fixtured.html"], templates=TREE) == 1
    out = capsys.readouterr().out
    assert "ACCESSIBILITY COVERAGE FAIL" in out
    assert "template: templates/orphan.html" in out
    assert "no route scenario or registered render fixture" in out


def test_5_dependency_changes_are_covered_through_extends_and_include(tmp_path):
    # layout.html and part.html have no scenario of their own; the fixture-rendered
    # page reaches both, and the route-rendered page reaches the layout.
    for name in ("layout.html", "part.html"):
        sub = tmp_path / name
        sub.mkdir()
        assert _run_guard(sub, changed=[name], routes=["route_only.html"], fixtures=["fixtured.html"],
                          templates=TREE) == 0, name


def test_5b_a_dependency_no_rendered_page_reaches_still_fails(tmp_path):
    assert _run_guard(tmp_path, changed=["part.html"], routes=["routed.html"], fixtures=[],
                      templates=TREE) == 1


def test_6_a_route_covered_template_needs_no_duplicate_fixture(tmp_path):
    assert _run_guard(tmp_path, changed=["routed.html"], routes=["routed.html"], fixtures=[],
                      templates=TREE) == 0


def test_8_removing_a_fixture_makes_the_guard_fail(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    kwargs = dict(changed=["fixtured.html"], routes=["route_only.html"], templates=TREE)
    assert _run_guard(before, fixtures=["fixtured.html"], **kwargs) == 0
    assert _run_guard(after, fixtures=[], **kwargs) == 1


def test_8b_registry_without_a_state_no_longer_covers_its_template():
    states = load_registry()
    covered_now = a11y_fixtures.fixture_templates(states)
    victim = "error_500.html"
    assert victim in covered_now
    remaining = [s for s in states if s.template != victim]
    assert victim not in a11y_fixtures.fixture_templates(remaining)
    assert guard.uncovered({victim}, guard.closure(
        guard.Environment(loader=guard.FileSystemLoader(str(TEMPLATES_DIR))),
        a11y_fixtures.fixture_templates(remaining)), {}) == [victim]


def test_an_exemption_for_a_template_that_is_covered_is_redundant_and_fails(tmp_path):
    assert _run_guard(tmp_path, changed=["fixtured.html"], routes=["route_only.html"], fixtures=["fixtured.html"],
                      exemptions={"fixtured.html": "stale"}, templates=TREE) == 1


# ---- the fixture renderer ----------------------------------------------------

def test_3_a_fixture_that_cannot_render_fails(app):
    def broken():
        raise KeyError("missing presentation field")
    with pytest.raises(FixtureRenderError, match="fixture cannot render"):
        render_state(flask_app, _state("error_404.html", broken))


def test_3b_a_context_missing_a_required_value_fails(app, probe_templates):
    probe_templates(**{"probe_needs_view.html": "{{ view.rows[0].name }}"})
    with pytest.raises(FixtureRenderError, match="fixture cannot render"):
        render_state(flask_app, _state("probe_needs_view.html", lambda: {"view": {"rows": []}}))


def test_a_fixture_that_queries_the_database_fails(app, probe_templates):
    from sqlalchemy import text

    from app.extensions import db

    def queries():
        db.session.execute(text("select 1"))
        return {}

    probe_templates(**{"probe_plain.html": "plain"})
    with pytest.raises(FixtureRenderError, match="touched the database"):
        render_state(flask_app, _state("probe_plain.html", queries))


def test_7_error_templates_render_from_presentation_input_alone(app):
    for state in (s for s in load_registry() if s.template.startswith("error_")):
        fixture = render_state(flask_app, state)
        assert fixture.templates >= {state.template}, state.id
        assert "<h1" in fixture.html, state.id


def test_7b_error_templates_still_render_without_a_query_once_wsgi_is_loaded(app):
    """Production serves ``wsgi:app``, and importing ``wsgi`` adds hooks to the shared app.

    One of them, ``inject_payroll_status``, ran ``PayrollSettings.query.first()``
    on every template render: an unscoped read of every class's settings whose
    result no template used. Tests run against the bare ``app.app``, so the gate
    passed or failed depending on whether an earlier test in the session had
    imported ``wsgi`` (two under ``tests/dom`` do). Importing it here makes the
    gate check what production actually renders.
    """
    import wsgi  # noqa: F401 -- registers wsgi's hooks on the shared app, as gunicorn does

    for state in (s for s in load_registry() if s.template.startswith("error_")):
        fixture = render_state(flask_app, state)
        assert fixture.templates >= {state.template}, state.id


def test_every_error_template_has_a_fixture_state():
    covered = a11y_fixtures.fixture_templates()
    errors = {p.name for p in TEMPLATES_DIR.glob("error_*.html")}
    assert errors, "no error templates found"
    assert errors <= covered, f"error templates without a fixture state: {sorted(errors - covered)}"


def test_every_registered_fixture_names_a_real_template():
    for state in load_registry():
        assert (TEMPLATES_DIR / state.template).exists(), state.id


# Per-render values the application itself randomises: CSRF tokens and the
# alert-card macro's element ids. Everything else must repeat exactly.
_CSRF_TOKEN = re.compile(r"[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{20,}|alert-card-\d+")


def test_fixture_registry_is_deterministic(app):
    """Repeated renders give the same DOM; only per-render random values differ."""
    for state in load_registry():
        first = _CSRF_TOKEN.sub("<csrf>", render_state(flask_app, state).html)
        second = _CSRF_TOKEN.sub("<csrf>", render_state(flask_app, state).html)
        assert first == second, state.id


# ---- axe over fixture markup (needs Chromium) --------------------------------

@pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")
def test_4_an_axe_violation_in_fixture_rendered_markup_fails(app, wcag_live_server, probe_templates):
    probe_templates(**{"probe_bad.html": _BAD_CONTRAST, "probe_good.html": _GOOD})
    states = [_state("probe_bad.html"), _state("probe_good.html")]
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            skip_or_fail_without_browser(exc)
        with browser:
            failures, rendered = audit_fixture_states(browser, wcag_live_server, states)

    assert set(failures) == {"probe_bad.html::default"}, failures
    report = failures["probe_bad.html::default"]
    assert "AXE FAIL" in report
    assert "template: templates/probe_bad.html" in report
    assert "state: default" in report
    assert "color-contrast" in report
    assert rendered >= {"probe_bad.html", "probe_good.html"}


@pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")
def test_a_fixture_that_cannot_render_is_reported_by_the_audit(app, wcag_live_server):
    def broken():
        raise RuntimeError("boom")
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover
            skip_or_fail_without_browser(exc)
        with browser:
            failures, rendered = audit_fixture_states(
                browser, wcag_live_server, [_state("error_404.html", broken)])
    assert "error_404.html::default" in failures
    assert "fixture cannot render" in failures["error_404.html::default"]
    assert rendered == set()
