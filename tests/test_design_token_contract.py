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


@pytest.fixture(scope="module")
def findings():
    return lint.scan()


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
