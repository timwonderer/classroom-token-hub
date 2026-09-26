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


# ==========================================================================
# TEMPORAL_ARITHMETIC_OUTSIDE_RESOLVER — INV-ARC-015 §VII, SPEC-TIME-001 §XII
# ==========================================================================

def _arithmetic_findings(source: str, path: str = "app/services/obligation_view_model.py"):
    return guardrails.check_temporal_arithmetic_outside_resolver(
        pathlib.Path(path), ast.parse(source), source
    )


def test_detects_the_rent_grace_deadline_defect_verbatim():
    """The view's grace fallback, as it shipped: 23:00 the previous class day
    after the November fall-back."""
    shipped = (
        "grace_end = due_date + timedelta(days=grace_period_days) if due_date else None\n"
    )
    findings = _arithmetic_findings(shipped)
    assert len(findings) == 1, findings
    assert findings[0].rule == "TEMPORAL_ARITHMETIC_OUTSIDE_RESOLVER"
    assert findings[0].line == 1


def test_detects_the_payroll_next_date_defect_verbatim():
    shipped = "candidate = first_pay + timedelta(days=freq_days * (periods_since_first + 1))\n"
    assert len(_arithmetic_findings(shipped, "app/routes/admin.py")) == 1


@pytest.mark.parametrize("shipped", [
    # The near miss a rewrite would reach for once the bare name is banned.
    "from datetime import timedelta as _td\nend = start + _td(days=1)\n",
    "import datetime as dt\nend = start + dt.timedelta(days=1)\n",
    "import datetime\nend = start + datetime.timedelta(days=1)\n",
])
def test_detects_every_spelling_of_timedelta(shipped):
    assert len(_arithmetic_findings(shipped)) == 1


def test_a_baseline_entry_does_not_travel_to_another_file():
    """The baseline freezes a line where it stood, not the construction."""
    frozen = "user.reset_code_expires_at = now + timedelta(minutes=10)\n"
    assert _arithmetic_findings(frozen, "app/services/student_recovery.py") == []
    assert len(_arithmetic_findings(frozen, "app/services/obligation_view_model.py")) == 1


def test_ignores_paths_outside_services_feats_and_routes():
    """The resolver itself is where this arithmetic belongs."""
    source = "end_local = start_local + timedelta(days=1)\n"
    assert _arithmetic_findings(source, "app/utils/canonical_temporal_resolver.py") == []


def test_ignores_mentions_that_are_not_calls():
    source = (
        '"""grace = due + timedelta(days=3) was the defect."""\n'
        "from datetime import timedelta\n"
        "# end = start + timedelta(days=1)\n"
        "def span() -> timedelta:\n"
        "    return None\n"
    )
    assert _arithmetic_findings(source) == []


def _arithmetic_sites():
    """(relative path, source line) of every timedelta call in scope."""
    sites = []
    for scope in guardrails.TEMPORAL_ARITHMETIC_SCOPES:
        for path in (REPO_ROOT / scope).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            relative = path.relative_to(REPO_ROOT).as_posix()
            for call in guardrails._timedelta_calls(ast.parse(text)):
                sites.append((relative, lines[call.lineno - 1].strip()))
    return sites


def test_no_timedelta_arithmetic_outside_the_resolver():
    offenders = [
        site for site in _arithmetic_sites()
        if site not in guardrails.TEMPORAL_ARITHMETIC_BASELINE
    ]
    assert not offenders, "timedelta arithmetic outside the resolver:\n  " + "\n  ".join(
        f"{path}: {source}" for path, source in offenders
    )


def test_the_temporal_arithmetic_baseline_only_shrinks():
    """A baseline entry with no matching line is a site that was fixed: remove
    it, so the line cannot quietly come back under the old allowance."""
    stale = guardrails.TEMPORAL_ARITHMETIC_BASELINE - set(_arithmetic_sites())
    assert not stale, (
        "remove fixed sites from TEMPORAL_ARITHMETIC_BASELINE in "
        "scripts/policy_guardrails.py:\n  " + "\n  ".join(sorted(map(str, stale)))
    )
