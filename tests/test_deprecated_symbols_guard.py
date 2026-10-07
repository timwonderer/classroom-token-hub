"""No deprecated symbol appears in first-party code (SOP-DB-002 §V, §VIII).

Runs on every pull request through ``policy-guardrails.yml``, and in the Schema
Change Gate, with ``--noconftest``: it needs no database. Before this guard the
scan ran only on pull requests that touched the model or migration paths, so a
change to a route, template or script that named a contracted symbol was never
scanned.

The detector lives in ``tests/guards/deprecated_symbols.py``. The mutation
proofs below feed it the spellings a future change would use (SOP-TEST-003
§IX.A).
"""
from __future__ import annotations

import re
from pathlib import Path

from tests.guards.deprecated_symbols import (
    REGISTRY_RELATIVE,
    find_deprecated_symbols,
    is_scanned,
    iter_scanned_files,
    parse_registry,
    scan_tree,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / REGISTRY_RELATIVE
SOP = ROOT / "docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-002_Deprecated_Symbols_Registry.md"


def _symbols() -> list[str]:
    return parse_registry(REGISTRY.read_text(encoding="utf-8"))


def _plant(tmp_path: Path, relative: str, text: str) -> None:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---- the guard on the real tree --------------------------------------------

def test_no_deprecated_symbol_in_first_party_code():
    hits = scan_tree(ROOT, _symbols())
    assert not hits, (
        "deprecated symbols found (SOP-DB-002 §VI):\n"
        + "\n".join(f"  {h.path}:{h.line}  {h.symbol}" for h in hits)
    )


def test_registry_is_enforcing_something():
    """An emptied registry passes the scan while enforcing nothing (the v1.2 state, SOP-DB-002 §X)."""
    symbols = _symbols()
    assert symbols
    assert len(symbols) == len(set(symbols)), "duplicate symbol in the registry"
    for symbol in symbols:
        assert not re.search(r"\s", symbol), f"symbols are single literals, not phrases: {symbol!r}"


def test_registry_matches_sop_enforced_table():
    """SOP-DB-002 §V: the document and the file list the same enforced symbols."""
    text = SOP.read_text(encoding="utf-8")
    section = text.split("## VI.", 1)[1].split("## VII.", 1)[0]
    documented = re.findall(r"^\|\s*`([^`]+)`\s*\|.*\|\s*Enforced\s*\|\s*$", section, flags=re.MULTILINE)
    assert documented, "no Enforced rows parsed from SOP-DB-002 §VI"
    assert sorted(documented) == sorted(_symbols())


def test_scan_still_reaches_every_root():
    """A renamed directory or suffix must not turn the guard into a no-op that keeps passing."""
    scanned = {p.relative_to(ROOT).as_posix() for p in iter_scanned_files(ROOT)}
    for expected in (
        "app/models.py",
        "app/routes/admin.py",
        "app/static/js/class_deletion_guardrails.js",
        "templates/student_shop.html",
        "scripts/policy_guardrails.py",
        "static/js/app-core.js",
        "static/sw.js",
    ):
        assert expected in scanned, expected
    assert any(p.endswith(".sh") for p in scanned)
    assert not any(p.startswith("static/vendor/") for p in scanned)


# ---- mutation proofs: the forbidden thing is committed and reported ---------

def test_mutation_aliased_import_in_python_is_reported(tmp_path):
    _plant(tmp_path, "app/routes/roster.py", "from app.models import ClassMembership as Membership\n")
    hits = scan_tree(tmp_path, _symbols())
    assert [(h.path, h.line, h.symbol) for h in hits] == [("app/routes/roster.py", 1, "ClassMembership")]


def test_mutation_template_attribute_is_reported(tmp_path):
    _plant(tmp_path, "templates/student_shop.html", "<p>\n{% if item.is_bundle %}Pack{% endif %}\n</p>\n")
    hits = scan_tree(tmp_path, _symbols())
    assert [(h.path, h.line, h.symbol) for h in hits] == [("templates/student_shop.html", 2, "is_bundle")]


def test_mutation_reflective_string_spelling_is_reported(tmp_path):
    """Defeats a name- or AST-based check: the symbol is only a string."""
    _plant(tmp_path, "app/models.py", 'presets = getattr(HallPassSettings, "get_default_pass_types")()\n')
    assert [h.symbol for h in scan_tree(tmp_path, _symbols())] == ["get_default_pass_types"]


def test_mutation_longer_identifier_is_reported(tmp_path):
    """Defeats a word-boundary check: a renamed wrapper still carries the preset."""
    _plant(tmp_path, "app/services/hall_pass.py", "def get_default_pass_types_for_class(class_id):\n    ...\n")
    assert [h.symbol for h in scan_tree(tmp_path, _symbols())] == ["get_default_pass_types"]


def test_mutation_static_js_is_reported(tmp_path):
    _plant(tmp_path, "static/js/store.js", "const uses = item.bundle_quantity || 1;\n")
    assert [h.path for h in scan_tree(tmp_path, _symbols())] == ["static/js/store.js"]


def test_mutation_service_worker_and_app_static_js_are_reported(tmp_path):
    _plant(tmp_path, "static/sw.js", "// cache BalanceCache reads\n")
    _plant(tmp_path, "app/static/js/roster.js", "fetch('/api/StudentBlock');\n")
    assert sorted(h.path for h in scan_tree(tmp_path, _symbols())) == [
        "app/static/js/roster.js",
        "static/sw.js",
    ]


def test_mutation_shell_script_is_reported(tmp_path):
    _plant(tmp_path, "scripts/backfill.sh", "psql -c 'select * from TeacherBlock'\n")
    assert [h.symbol for h in scan_tree(tmp_path, _symbols())] == ["TeacherBlock"]


# ---- lawful inputs stay quiet -----------------------------------------------

def test_lawful_neighbours_are_not_reported():
    text = (
        "from app.models import ClassEconomy, Seat\n"
        "settings.get_pass_types()\n"
        "item.bulk_discount_enabled and item.bulk_discount_quantity\n"
        "_get_balance_cache(seat_id, class_id)\n"
    )
    assert find_deprecated_symbols("app/x.py", text, _symbols()) == []


def test_out_of_scope_paths_are_not_scanned(tmp_path):
    """Third-party code, tests, docs and migrations name retired symbols lawfully."""
    for relative in (
        "static/vendor/bootstrap/js/bootstrap.js",
        "static/css/app.css",
        "tests/test_store.py",
        "docs/history.md",
        "migrations/versions/0001_drop_class_membership.py",
        "app/data/legacy.txt",
    ):
        _plant(tmp_path, relative, "ClassMembership is_bundle\n")
        assert not is_scanned(relative), relative
    assert scan_tree(tmp_path, _symbols()) == []


def test_registry_parsing_ignores_comments_and_blank_lines():
    text = "# header\n\nClassMembership\n  # indented comment\n  is_bundle  \n"
    assert parse_registry(text) == ["ClassMembership", "is_bundle"]
