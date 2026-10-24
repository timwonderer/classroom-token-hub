"""Class-scoped deadlines must resolve in the class timezone (findings 25, 26).

SPEC-TIME-001 §I makes ``canonical_temporal_resolver`` the only public temporal
evaluation helper, and §CLE names the class-scoped cases: obligation due dates,
payroll, store expiry, class-local day boundaries. That rule existed the whole
time. What did not exist was a control, so it regressed three times in code
written by people who knew it — most recently in a remediation whose own commit
message named the defect class.

The distinction finding 26 draws is the point of this file. INV-ARC-007 ("no
writes on GET") is a rule WITH a control and cannot regress silently.
SPEC-TIME-001 was a rule without one. These tests exist so that stops being true,
and — per SOP-TEST-003 §IX.A — they prove the detector detects, rather than
merely observing that a repaired tree is clean.
"""

from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_guardrails():
    spec = importlib.util.spec_from_file_location(
        "policy_guardrails", REPO_ROOT / "scripts" / "policy_guardrails.py"
    )
    module = importlib.util.module_from_spec(spec)
    # @dataclass resolves annotations through sys.modules[cls.__module__], so the
    # module must be registered before it executes or every dataclass in the
    # script raises AttributeError on a None module.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


guardrails = _load_guardrails()


def _findings(source: str):
    tree = ast.parse(source)
    return guardrails.check_class_scoped_temporal_authority(
        pathlib.Path("app/routes/admin.py"), tree
    )


# --------------------------------------------------------------------------
# Mutation proofs — the constructions that actually shipped
# --------------------------------------------------------------------------

def test_detects_the_rent_due_date_defect_verbatim():
    """Finding 25, exactly as it was written in app/routes/admin.py."""
    shipped = """
payload = {
    'first_rent_due_date': (
        datetime.strptime(first_due_date_str, '%Y-%m-%d')
        if first_due_date_str else None
    ),
}
"""
    findings = _findings(shipped)
    assert len(findings) == 1, findings
    assert findings[0].rule == "CLASS_SCOPED_TEMPORAL_AUTHORITY"
    assert "first_rent_due_date" in findings[0].message
    assert "strptime" in findings[0].message


def test_detects_the_payroll_first_pay_date_defect():
    """Finding 6A's first site, as a keyword argument rather than a dict key."""
    shipped = "update_payroll_settings(first_pay_date=datetime.strptime(raw, '%Y-%m-%d'))"
    assert len(_findings(shipped)) == 1


def test_detects_an_attribute_assignment():
    """The third spelling: written straight onto a model instance."""
    shipped = "settings.next_payroll_date = datetime.strptime(raw, '%Y-%m-%d')"
    assert len(_findings(shipped)) == 1


def test_detects_datetime_combine_which_is_the_same_defect_spelled_longer():
    shipped = "product.activation_at = datetime.combine(picked_date, time.min)"
    assert len(_findings(shipped)) == 1


@pytest.mark.parametrize(
    "column",
    sorted(guardrails.CLASS_SCOPED_TEMPORAL_COLUMNS),
)
def test_every_enumerated_column_is_actually_checked(column):
    """A column named in the list but unreachable by the detector guards nothing."""
    shipped = f"row.{column} = datetime.strptime(raw, '%Y-%m-%d')"
    assert len(_findings(shipped)) == 1, f"{column} is listed but not detected"


@pytest.mark.parametrize("call", ["today", "now", "utcnow", "fromtimestamp"])
def test_server_clock_sources_are_rejected(call):
    """The server's clock is not the class's calendar."""
    shipped = f"row.cycle_boundary_at = datetime.{call}()"
    assert len(_findings(shipped)) == 1


# --------------------------------------------------------------------------
# The detector must not report correct code
# --------------------------------------------------------------------------

def test_accepts_the_cle_helper():
    """The shape the fix actually uses."""
    fixed = "payload = {'first_rent_due_date': _class_local_date_start_utc(raw)}"
    assert _findings(fixed) == []


def test_accepts_a_resolver_boundary():
    fixed = """
bounds = canonical_temporal_resolver(
    CLASS_LEVEL_EVALUATION,
    canonical_execution_context=ctx,
    primitive="evaluation_day_boundaries",
    evaluation_date=parsed,
)
row.cycle_boundary_at = bounds.boundary_start_utc
"""
    assert _findings(fixed) == []


def test_accepts_a_value_passed_through():
    """A resolved instant handed on from a schedule service is not a new parse."""
    fixed = "schedule_next_bill_cycle(cycle_boundary_at=schedule.cycle_boundary_at)"
    assert _findings(fixed) == []


def test_ignores_a_naive_parse_that_is_not_a_class_scoped_deadline():
    """The rule governs class-scoped deadline columns, not every strptime.

    Report date filters are a different and separately-assessed defect class
    (finding 25's closing note); flagging them here would produce noise that
    gets the rule waived.
    """
    unrelated = "start = datetime.strptime(start_date, '%Y-%m-%d')"
    assert _findings(unrelated) == []


# --------------------------------------------------------------------------
# The live assertion
# --------------------------------------------------------------------------

def test_the_application_tree_is_clean():
    """No class-scoped deadline in app/ is written from a naive construction."""
    offenders = []
    for path in (REPO_ROOT / "app").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
        offenders += guardrails.check_class_scoped_temporal_authority(path, tree)

    assert not offenders, "class-scoped deadlines bypassing CLE:\n  " + "\n  ".join(
        f"{f.path.relative_to(REPO_ROOT)}:{f.line} {f.message}" for f in offenders
    )
