"""Structural guard: payroll_settings is read only through the one resolver.

Operator ruling 2026-09-30 (DOM-POL-001 §VI.2). The detector lives in
``tests/guards/payroll_settings_reads.py``; the mutation proofs below feed it the
spellings a future change would really use and assert each is reported
(SOP-TEST-003 §IX.A), so a green run means "no violation" rather than "the
detector stopped detecting".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.guards.payroll_settings_reads import RESOLVER_MODULE, find_violations

REPO = Path(__file__).resolve().parents[1]


def _app_sources():
    for path in sorted((REPO / "app").rglob("*.py")):
        yield str(path.relative_to(REPO)), path.read_text(encoding="utf-8")


def test_no_module_outside_the_resolver_queries_payroll_settings():
    violations = [
        violation
        for path, source in _app_sources()
        for violation in find_violations(path, source)
    ]
    assert not violations, "\n".join(str(v) for v in violations)


def test_the_resolver_is_where_the_queries_are():
    """The allowlisted module really does hold the queries — the guard is not
    passing because the table stopped being read at all."""
    source = (REPO / RESOLVER_MODULE).read_text(encoding="utf-8")
    assert "PayrollSettings.query" in source
    assert find_violations("app/elsewhere.py", source)


@pytest.mark.parametrize("snippet", [
    # The pre-2026-09-30 route-local read this guard exists to stop.
    "from app.models import PayrollSettings\n"
    "row = PayrollSettings.query.filter_by(class_id=c, availability_state='IN_USE').first()\n",
    "from app.models import PayrollSettings as PS\nrow = PS.query.filter_by(class_id=c).first()\n",
    "from app import models\nrow = models.PayrollSettings.query.first()\n",
    "from app.models import PayrollSettings\nrate = db.session.query(PayrollSettings.pay_rate).scalar()\n",
    "import sqlalchemy as sa\nfrom app.models import PayrollSettings\n"
    "stmt = sa.select(PayrollSettings).where(PayrollSettings.class_id == c)\n",
    "from app.models import PayrollSettings\nrow = db.session.get(PayrollSettings, uid)\n",
    "from sqlalchemy import text\n"
    "rate = db.session.execute(text('SELECT pay_rate FROM payroll_settings WHERE class_id = :c'))\n",
    "q = Seat.query.join(PayrollSettings, PayrollSettings.class_id == Seat.class_id)\n",
])
def test_mutation_proof__each_direct_read_is_reported(snippet):
    assert find_violations("app/routes/example.py", snippet), snippet


def test_mutation_proof__prose_and_the_resolver_are_not_reported():
    prose = '"""Payroll reads nothing else: every read goes to payroll_settings."""\n'
    assert find_violations("app/routes/example.py", prose) == []
    read = "from app.models import PayrollSettings\nPayrollSettings.query.first()\n"
    assert find_violations(RESOLVER_MODULE, read) == []


# --------------------------------------------------------------------------- #
# No stored or hard-coded pay frequency (operator ruling 2026-09-30)          #
# --------------------------------------------------------------------------- #

from tests.guards.payroll_frequency import find_violations as find_frequency_violations  # noqa: E402


def test_no_stored_or_day_count_pay_frequency_in_app():
    violations = [
        violation
        for path, source in _app_sources()
        for violation in find_frequency_violations(path, source)
    ]
    assert not violations, "\n".join(str(v) for v in violations)


@pytest.mark.parametrize("path,snippet", [
    # The dropped column coming back, in each spelling.
    ("app/routes/admin.py", "settings_data = {'payroll_frequency_days': 14}\n"),
    ("app/routes/admin.py", "days = setting.payroll_frequency_days\n"),
    ("app/services/payroll/settings.py", "PayrollSettings(payroll_frequency_days=14)\n"),
    ("app/models.py", "payroll_frequency_days = db.Column(db.Integer)\n"),
    # A month or schedule approximated as days in payroll code.
    ("app/services/payroll/schedule.py", "nxt = last + timedelta(days=30)\n"),
    ("app/services/payroll/schedule.py", "NOMINAL = {'weekly': 7, 'biweekly': 14, 'monthly': 30}\n"),
    ("app/utils/economy_balance.py", "period = advance(start, days=31)\n"),
])
def test_mutation_proof__each_frequency_violation_is_reported(path, snippet):
    assert find_frequency_violations(path, snippet), snippet


def test_mutation_proof__non_payroll_day_arithmetic_and_labels_are_not_reported():
    # Rent and banking keep their own cadences; only payroll modules are held.
    assert find_frequency_violations("app/routes/api.py", "grace = timedelta(days=30)\n") == []
    # Schedule names mapped to labels, not numbers, are fine in payroll code.
    assert find_frequency_violations(
        "app/services/payroll/schedule.py", "LABELS = {'monthly': 'month'}\n"
    ) == []
