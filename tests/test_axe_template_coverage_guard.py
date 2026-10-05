"""Mutation proofs for scripts/check_axe_template_coverage.py (SOP-TEST-003 §IX.A)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_SPEC = importlib.util.spec_from_file_location(
    "check_axe_template_coverage",
    Path(__file__).resolve().parent.parent / "scripts" / "check_axe_template_coverage.py",
)
guard = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(guard)


def _run(tmp_path, templates, changed, rendered, exemptions=None):
    tdir = tmp_path / "templates"
    tdir.mkdir()
    for name, body in templates.items():
        (tdir / name).parent.mkdir(parents=True, exist_ok=True)
        (tdir / name).write_text(body, encoding="utf-8")
    changed_file = tmp_path / "changed.txt"
    changed_file.write_text("\n".join(f"templates/{n}" for n in changed), encoding="utf-8")
    rendered_file = tmp_path / "rendered.json"
    rendered_file.write_text(json.dumps(rendered), encoding="utf-8")
    argv = ["--changed", str(changed_file), "--rendered", str(rendered_file),
            "--templates-dir", str(tdir),
            "--exemptions", str(tmp_path / "ex.json")]
    if exemptions is not None:
        (tmp_path / "ex.json").write_text(json.dumps(exemptions), encoding="utf-8")
    return guard.main(argv)


TEMPLATES = {
    "layout.html": "<html>{% block c %}{% endblock %}</html>",
    "page.html": "{% extends 'layout.html' %}{% include 'frag.html' %}{% from 'macros/m.html' import x %}",
    "frag.html": "<p>frag</p>",
    "macros/m.html": "{% macro x() %}x{% endmacro %}",
    "orphan.html": "<p>never rendered</p>",
}


def test_unrendered_changed_template_fails(tmp_path):
    assert _run(tmp_path, TEMPLATES, ["orphan.html"], ["page.html"]) == 1


def test_template_reached_through_extends_include_import_passes(tmp_path):
    for name in ("layout.html", "frag.html", "macros/m.html", "page.html"):
        sub = tmp_path / name.replace("/", "_")
        sub.mkdir()
        assert _run(sub, TEMPLATES, [name], ["page.html"]) == 0, name


def test_exemption_allows_but_stale_exemption_fails(tmp_path):
    first = tmp_path / "a"
    first.mkdir()
    assert _run(first, TEMPLATES, ["orphan.html"], ["page.html"], {"orphan.html": "why"}) == 0
    second = tmp_path / "b"
    second.mkdir()
    assert _run(second, TEMPLATES, ["page.html"], ["page.html"], {"gone.html": "why"}) == 1


def test_empty_or_missing_sweep_record_fails(tmp_path):
    assert _run(tmp_path, TEMPLATES, ["page.html"], []) == 1


def test_non_template_changes_need_no_coverage(tmp_path):
    assert _run(tmp_path, TEMPLATES, [], ["page.html"]) == 0


def test_closure_follows_nested_references():
    env = Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent / "templates")))
    assert "layout_system_admin.html" in guard.closure(env, {"sysadmin_support_tickets.html"})
