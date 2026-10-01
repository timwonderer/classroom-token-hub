"""DOM-CLASS-003 §VII: a payroll change saved mid-cycle governs the next cycle.

Operator ruling 2026-09-30. A teacher who changes the pay rate while a payroll
cycle is open must not reprice work already done: that work is paid at the rate
it was done under, and the new rate governs from the next payroll date. Before
the fix, saving a new rate replaced the one in force at once, and the next run —
manual or automatic — paid every unpaid session at the new rate. A probe on
2026-09-29 paid 15 minutes worked at $1/min as $150 after a save of $10/min.

These tests drive the real routes (POST /admin/payroll/settings, POST
/admin/run_payroll) and the real automatic-payroll job, and read the ledger.
Attendance rows are written directly as timeline fixtures, as the other payroll
tests do; the clock is pinned so each row, save and run lands at a chosen
instant (the resolver's clock is the only one application code reads).

The class is in America/Los_Angeles. The first pay date, Fri Oct 9 2026, starts
at 07:00 UTC.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import app.utils.canonical_temporal_resolver as resolver_module
from app.extensions import db
from app.feats.base import FEATContext
from app.models import AttendanceSession, Transaction
from app.scheduled_tasks import run_automatic_payroll_job
from tests.helpers.canonical_classroom import login_teacher
from tests.helpers.class_domain import enable_class_feature, update_payroll_settings
from tests.helpers.classroom_initializer import initialize_as_teacher


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


MON = _utc(2026, 10, 5, 16, 0)      # 09:00 PDT, Mon Oct 5 — cycle 1 is open
FIRST_PAY = _utc(2026, 10, 9, 7, 0)  # 00:00 PDT, Fri Oct 9 — the next payroll date
AFTER = _utc(2026, 10, 12, 16, 0)    # 09:00 PDT, Mon Oct 12 — cycle 2


@contextmanager
def _clock(monkeypatch, instant):
    class _Pinned(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    with monkeypatch.context() as patch:
        patch.setattr(resolver_module, "datetime", _Pinned)
        yield


def _login(client, classroom, instant):
    """A teacher session whose activity clock reads ``instant`` (the session
    helper stamps the real wall clock, which a pinned clock would read as idle)."""
    login_teacher(client, classroom)
    with client.session_transaction() as sess:
        sess["login_time"] = sess["last_activity"] = instant.isoformat()


def _save_rate(client, dollars_per_hour: str):
    response = update_payroll_settings(
        client,
        settings_mode="simple",
        simple_pay_rate=dollars_per_hour,
        simple_frequency="biweekly",
        simple_first_pay_date="2026-10-09",
    )
    assert response.status_code == 302, response.get_data(as_text=True)
    with client.session_transaction() as sess:
        flashes = sess.pop("_flashes", [])
    assert not [message for category, message in flashes if category == "error"], flashes


def _work(classroom, seat_id: int, start: datetime, minutes: int) -> None:
    with FEATContext(
        "FEAT-PROD-001", correlation_id=f"att:{uuid4()}", idempotency_key=f"att:{uuid4()}"
    ):
        for status, instant in (("active", start), ("inactive", start + timedelta(minutes=minutes))):
            db.session.add(AttendanceSession(
                target_seat_id=seat_id, class_id=classroom.class_id,
                actor_seat_id=classroom.teacher_seat_id, status=status,
                reason_code="start_work" if status == "active" else "done_for_day",
                timestamp=instant,
            ))
        db.session.flush()
    db.session.commit()


def _payroll_credits(classroom, seat_id: int) -> list[Decimal]:
    rows = (
        Transaction.query
        .filter_by(class_id=classroom.class_id, seat_id=seat_id, type="payroll")
        .order_by(Transaction.timestamp.asc(), Transaction.id.asc())
        .all()
    )
    return [Decimal(str(row.amount)).quantize(Decimal("0.01")) for row in rows]


def _setup(client, app, monkeypatch):
    """R1 = $60/hour ($1/min) in force; 15 minutes worked under it; then R2 =
    $600/hour ($10/min) saved while the cycle is still open."""
    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    enable_class_feature(class_id=classroom.class_id, feature="payroll")
    seat_id = classroom.students[0].seat.id

    with _clock(monkeypatch, MON):
        _login(client, classroom, MON)
        _save_rate(client, "60.00")
    _work(classroom, seat_id, MON + timedelta(minutes=5), 15)
    with _clock(monkeypatch, MON + timedelta(minutes=30)):
        _login(client, classroom, MON + timedelta(minutes=30))
        _save_rate(client, "600.00")
    return classroom, seat_id


def test_DOM_CLASS_003__teacher_run_pays_open_cycle_work_at_the_rate_it_was_done_under(
    client, app, monkeypatch
):
    classroom, seat_id = _setup(client, app, monkeypatch)

    with _clock(monkeypatch, MON + timedelta(minutes=35)):
        _login(client, classroom, MON + timedelta(minutes=35))
        response = client.post("/admin/run_payroll", data={"idempotency_token": "run-1"})
        assert response.status_code == 302, response.get_data(as_text=True)

    # 15 minutes at $1/min — not at the $10/min saved after the work was done.
    assert _payroll_credits(classroom, seat_id) == [Decimal("15.00")]


def test_DOM_CLASS_003__automatic_run_pays_open_cycle_work_at_the_rate_it_was_done_under(
    client, app, monkeypatch
):
    classroom, seat_id = _setup(client, app, monkeypatch)

    # The scheduled run on the first pay date settles cycle 1.
    with _clock(monkeypatch, FIRST_PAY + timedelta(minutes=30)):
        run_automatic_payroll_job()

    assert _payroll_credits(classroom, seat_id) == [Decimal("15.00")]


def test_DOM_CLASS_003__the_saved_rate_governs_work_after_the_payroll_date(
    client, app, monkeypatch
):
    classroom, seat_id = _setup(client, app, monkeypatch)

    with _clock(monkeypatch, FIRST_PAY + timedelta(minutes=30)):
        run_automatic_payroll_job()
    # 15 minutes of cycle-2 work, after the boundary.
    _work(classroom, seat_id, AFTER, 15)
    with _clock(monkeypatch, AFTER + timedelta(minutes=30)):
        _login(client, classroom, AFTER + timedelta(minutes=30))
        response = client.post("/admin/run_payroll", data={"idempotency_token": "run-2"})
        assert response.status_code == 302, response.get_data(as_text=True)

    assert _payroll_credits(classroom, seat_id) == [Decimal("15.00"), Decimal("150.00")]


def test_DOM_CLASS_003__a_manual_run_does_not_bring_the_saved_rate_forward(
    client, app, monkeypatch
):
    """Running payroll early settles work; it is not the payroll date, so the
    rate saved for that date still waits for it."""
    classroom, seat_id = _setup(client, app, monkeypatch)

    with _clock(monkeypatch, MON + timedelta(minutes=35)):
        _login(client, classroom, MON + timedelta(minutes=35))
        client.post("/admin/run_payroll", data={"idempotency_token": "early"})
    # More cycle-1 work, before the payroll date, after the early run.
    tue = MON + timedelta(days=1)
    _work(classroom, seat_id, tue, 15)
    with _clock(monkeypatch, tue + timedelta(minutes=30)):
        _login(client, classroom, tue + timedelta(minutes=30))
        response = client.post("/admin/run_payroll", data={"idempotency_token": "early-2"})
        assert response.status_code == 302, response.get_data(as_text=True)

    assert _payroll_credits(classroom, seat_id) == [Decimal("15.00"), Decimal("15.00")]
