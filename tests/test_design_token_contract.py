"""SPEC-DES-001 §XIV: the template contract is gated, not reviewed by eye.

Each rule is its own test so a failure names the law that broke. The scanner
lives in ``scripts/lint_design_tokens.py`` so the same check runs from the
command line while a template is being edited.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "lint_design_tokens", REPO_ROOT / "scripts" / "lint_design_tokens.py"
)
lint = importlib.util.module_from_spec(_spec)
# dataclasses resolve their defining module through sys.modules.
sys.modules[_spec.name] = lint
_spec.loader.exec_module(lint)

RULES = {
    "R1": "no hardcoded colour in markup, <style>, or template script",
    "R5": "no inline style attribute that is static on every render",
    "R6": "no literal design value in a <style> block or computed style attribute",
    "R7": "no selector in a template <style> block that style.css also defines",
}

SURFACE_RULES = {
    "R8": "no colour literal outside a token definition, on any brand surface",
    "R9": "no var(--token) that the surface's token layer does not define",
    "R10": "a stylesheet that is meant to be a copy of another still is one",
}


@pytest.fixture(scope="module")
def findings():
    return lint.scan()


@pytest.fixture(scope="module")
def surface_findings():
    return lint.scan_surfaces() + lint.scan_mirrors()


@pytest.mark.parametrize("rule", sorted(RULES))
def test_SPEC_DES_001__templates_conform(findings, rule):
    violations = [str(f) for f in findings if f.rule == rule]
    assert not violations, f"{rule}: {RULES[rule]}\n" + "\n".join(violations)


@pytest.mark.parametrize(
    ("markup", "rule"),
    [
        ('<p style="color: #fff">x</p>', "R5"),
        ('<style>.x { color: #6c757d; }</style>', "R1"),
        ('<style>.x { border: 1px solid white; }</style>', "R1"),
        ('<style>.x { color: var(--secondary, #d4a857); }</style>', "R1"),
        ("<script>const c = '#198754';</script>", "R1"),
        ('<style>.x { font-size: 0.85rem; }</style>', "R6"),
        ('<style>.x { padding: 1rem 2rem; }</style>', "R6"),
        ('<style>.x { transition: all 0.3s ease; }</style>', "R6"),
        ('<style>.x { opacity: 0.3; }</style>', "R6"),
        ('<div style="width: {{ pct }}%; font-size: 14px"></div>', "R6"),
        ('<style>.btn-primary { background: var(--primary); }</style>', "R7"),
        # HTML lets whitespace and ignored attributes sit in an end tag, so a block
        # closed with `</style >` is a real block and must not slip past the scanner.
        ('<style>.x { color: #6c757d; }</style >', "R1"),
        ('<style>.x { font-size: 0.85rem; }</style\n>', "R6"),
        ("<script>const c = '#198754';</script >", "R1"),
    ],
)
def test_scanner_detects_each_rule(tmp_path, monkeypatch, markup, rule):
    """Guard against the gate going green because the scanner went blind."""
    page = tmp_path / "templates" / "probe.html"
    page.parent.mkdir()
    page.write_text(markup, encoding="utf-8")
    monkeypatch.setattr(lint, "REPO_ROOT", tmp_path)
    assert rule in {f.rule for f in lint.scan_file(page)}


@pytest.mark.parametrize(
    "markup",
    [
        '<div class="progress-bar" style="width: {{ pct }}%"></div>',
        '<style>.x { color: var(--text-secondary); padding: var(--space-4); }</style>',
        '<style>.x { min-height: 100dvh; border-radius: 50%; grid-template-columns: 1fr 1fr auto; }</style>',
        '<style>.x { max-width: 200px; border-left: 4px solid var(--border-color); }</style>',
        '<a href="#add">Add</a><button data-bs-target="#fff">x</button>',
        "<script>document.querySelector('#bad').hidden = true;</script>",
    ],
)
def test_scanner_admits_tokens_structure_and_selectors(tmp_path, monkeypatch, markup):
    """Structural geometry and id selectors are not design values (§IX)."""
    page = tmp_path / "templates" / "probe.html"
    page.parent.mkdir()
    page.write_text(markup, encoding="utf-8")
    monkeypatch.setattr(lint, "REPO_ROOT", tmp_path)
    assert lint.scan_file(page) == []


# ─── §XIII surfaces: the app is not the only brand surface ───


@pytest.mark.parametrize("rule", sorted(SURFACE_RULES))
def test_SPEC_DES_001__every_surface_conforms(surface_findings, rule):
    violations = [str(f) for f in surface_findings if f.rule == rule]
    assert not violations, f"{rule}: {SURFACE_RULES[rule]}\n" + "\n".join(violations)


def _sheet(tmp_path, monkeypatch, css, *, tokens=""):
    monkeypatch.setattr(lint, "REPO_ROOT", tmp_path)
    path = tmp_path / "surface.css"
    path.write_text(css, encoding="utf-8")
    defined = set()
    if tokens:
        tok = tmp_path / "tokens.css"
        tok.write_text(tokens, encoding="utf-8")
        defined = lint.token_definitions([tok])
    return path, defined


@pytest.mark.parametrize(
    ("css", "rule"),
    [
        # R8 — the literal spellings a real regression would actually use
        (".x { color: #6c757d; }", "R8"),
        (".x { background: #D4A857; }", "R8"),
        (".x { color: white; }", "R8"),
        (".x { border: 1px solid rgb(212, 168, 87); }", "R8"),
        # the v1 gold in rgba form, which is how it survived the hex sweep
        (".x { outline: 3px solid rgba(211, 175, 55, .35); }", "R8"),
        # a fallback that restates the token it shadows
        (".x { color: var(--sidebar-text, #ffffff); }", "R8"),
        # a theme block is a token block, but only for the properties it defines
        ("body.student-shell { --primary: #2F4F7F; color: #2F4F7F; }", "R8"),
        # R9 — a token name from another surface, which is how --secondary-color
        # leaked into the app stylesheet and fell back silently on seven lines
        (".x { color: var(--secondary-color); }", "R9"),
        (".x { padding: var(--space-nope); }", "R9"),
    ],
)
def test_surface_scanner_detects_each_rule(tmp_path, monkeypatch, css, rule):
    """Guard against the gate going green because the scanner went blind."""
    path, defined = _sheet(tmp_path, monkeypatch, css, tokens=":root { --secondary: #D4A857; }")
    assert rule in {f.rule for f in lint.scan_stylesheet(path, defined, ())}


@pytest.mark.parametrize(
    ("css", "tokens"),
    [
        # defining a token is the one place a literal belongs
        (":root { --primary: #1a4d47; --shadow-sm: 0 1px 2px rgba(0,0,0,.04); }", ""),
        ("body.sysadmin-shell { --primary: #303030; }", ""),
        # achromatic operands inside a colour function are shading, not colour
        (".x { border: 1px solid color-mix(in srgb, var(--primary) 80%, black); }",
         ":root { --primary: #1a4d47; }"),
        (".x { box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08); }", ""),
        (".x { background: rgba(255, 255, 255, 0.35); }", ""),
        # a defined token resolves
        (".x { color: var(--primary); }", ":root { --primary: #1a4d47; }"),
    ],
)
def test_surface_scanner_admits_definitions_and_shading(tmp_path, monkeypatch, css, tokens):
    path, defined = _sheet(tmp_path, monkeypatch, css, tokens=tokens)
    assert lint.scan_stylesheet(path, defined, ()) == []


def test_surface_scanner_admits_framework_prefixes(tmp_path, monkeypatch):
    """Infima and Bootstrap own their own namespaces; this project does not define them."""
    path, defined = _sheet(tmp_path, monkeypatch, ".x { color: var(--ifm-color-primary); }")
    assert lint.scan_stylesheet(path, defined, ("--ifm-",)) == []
    assert "R9" in {f.rule for f in lint.scan_stylesheet(path, defined, ())}


def test_mirror_scanner_detects_a_fork(tmp_path, monkeypatch):
    """The status service's copy of the public stylesheet drifted for a day and
    nothing reported it; a one-byte divergence must be a failure."""
    monkeypatch.setattr(lint, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(lint, "MIRRORS", (("source.css", "copy.css"),))
    (tmp_path / "source.css").write_text(":root { --secondary: #D4A857; }", encoding="utf-8")
    (tmp_path / "copy.css").write_text(":root { --secondary: #d3af37; }", encoding="utf-8")
    assert "R10" in {f.rule for f in lint.scan_mirrors()}

    (tmp_path / "copy.css").write_text(":root { --secondary: #D4A857; }", encoding="utf-8")
    assert lint.scan_mirrors() == []
