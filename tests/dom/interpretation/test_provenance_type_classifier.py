"""§6.3 student-originated provenance classifier (SPEC-ITR-001 v1.4 owner
ruling; ``DOM-ITR-001`` INV-ITR-015 v1.9).

The classifier no longer consults ``feat_code`` at all -- it classifies by
``mechanism`` plus a closed ``Transaction.type`` exclusion set
(``SYSTEM_ORIGINATED_TYPE_VALUES`` in
``app/services/ledger_provenance_query_service.py``). The ``type`` clause is
documented as redundant with, not a replacement for, ``mechanism``: every
excluded type is already produced only under ``mechanism != SELF`` by a
correctly-attributing writer, so the clause exists purely as a second,
independent check against a writer supplying the wrong ``mechanism`` for an
otherwise-recognizable system event.

Positive cases below plant a feat_code the old (removed)
``SYSTEM_ORIGINATED_FEAT_CODES`` set used to exclude, proving feat_code no
longer gates the result (SOP-TEST-003 §IX.A / testing.md Mistake 6a). The
"wrong mechanism" cases plant mechanism=self on a row carrying a system type,
which is exactly the scenario the type clause exists to catch independently
of mechanism -- confirmed mutation-sensitive by temporarily dropping the
type clause and observing those two tests go red.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.feats.base import FEATContext
from app.services.ledger_provenance_query_service import (
    SYSTEM_ORIGINATED_TYPE_VALUES,
    get_seat_ids_with_student_originated_activity,
    get_student_originated_rows,
    get_student_originated_transaction_ids,
    get_student_savings_contribution_rows,
)
from tests.helpers.ledger import provision_ledger_classroom, record_ledger_fixture

WINDOW_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 1, 2, tzinfo=timezone.utc)
WITHIN_WINDOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _row(classroom, *, feat_name, mechanism="self", account_type="checking",
         amount, type, idempotency_suffix):
    seat_id = classroom.students[0].seat_id
    with FEATContext(feat_name, idempotency_key=f"provenance:{feat_name}:{idempotency_suffix}"):
        return record_ledger_fixture(
            seat_id=seat_id,
            class_id=classroom.class_id,
            amount=amount,
            account_type=account_type,
            type=type,
            mechanism=mechanism,
            description=f"{feat_name}/{type} fixture",
            timestamp=WITHIN_WINDOW,
        )


# --- The exclusion set itself ------------------------------------------------


def test_system_originated_type_values_closed_set():
    assert SYSTEM_ORIGINATED_TYPE_VALUES == frozenset(
        {"payroll", "payroll_correction", "interest", "Interest", "overdraft_fee"}
    )


# --- Positive: feat_code no longer gates the result -------------------------


def test_feat_obl_003_payment_counts_as_student_originated_regardless_of_feat_code(client, app):
    """FEAT-OBL-003 was in the old, now-removed SYSTEM_ORIGINATED_FEAT_CODES
    set. Planting it here with a non-system type proves feat_code is no
    longer consulted -- this would have been excluded under the removed set."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat_id = classroom.students[0].seat_id
    txn = _row(
        classroom, feat_name="FEAT-OBL-003", amount=-5,
        type="insurance_premium", idempotency_suffix="premium",
    )

    seat_ids = get_seat_ids_with_student_originated_activity(
        classroom.class_id, WINDOW_START, WINDOW_END
    )
    assert seat_id in seat_ids

    rows = get_student_originated_rows(classroom.class_id, WINDOW_START, WINDOW_END)
    assert any(r.seat_id == seat_id and r.amount_cents == -500 for r in rows)

    ids = get_student_originated_transaction_ids(classroom.class_id, [txn.id])
    assert txn.id in ids


def test_feat_led_005_transfer_legs_count_as_student_originated(client, app):
    """FEAT-LED-000/FEAT-LED-005 was also in the removed set. A transfer's
    legs use ``type='Withdrawal'``/``'Deposit'`` -- neither is in the closed
    system-type exclusion set, so both legs count."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat_id = classroom.students[0].seat_id
    deposit = _row(
        classroom, feat_name="FEAT-LED-005", account_type="savings",
        amount=25, type="Deposit", idempotency_suffix="transfer-deposit",
    )

    seat_ids = get_seat_ids_with_student_originated_activity(
        classroom.class_id, WINDOW_START, WINDOW_END
    )
    assert seat_id in seat_ids
    ids = get_student_originated_transaction_ids(classroom.class_id, [deposit.id])
    assert deposit.id in ids

    rows = get_student_savings_contribution_rows(classroom.class_id, WINDOW_START, WINDOW_END)
    assert any(r.seat_id == seat_id and r.amount_cents == 2500 for r in rows)


# --- Negative: the type clause independently excludes system types ---------
#
# These simulate a writer that supplied mechanism=self on a system-type row
# (the exact bug the type clause is a second check against): mechanism alone
# would NOT exclude these rows, so a green result here depends on the type
# clause actually running.


def test_payroll_type_excluded_even_under_wrong_mechanism(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat_id = classroom.students[0].seat_id
    txn = _row(
        classroom, feat_name="FEAT-LED-004", mechanism="self",
        amount=10, type="payroll", idempotency_suffix="wrong-mechanism-payroll",
    )

    seat_ids = get_seat_ids_with_student_originated_activity(
        classroom.class_id, WINDOW_START, WINDOW_END
    )
    assert seat_id not in seat_ids
    ids = get_student_originated_transaction_ids(classroom.class_id, [txn.id])
    assert ids == set()


def test_legacy_cased_interest_type_excluded_even_under_wrong_mechanism(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat_id = classroom.students[0].seat_id
    txn = _row(
        classroom, feat_name="FEAT-LED-001", mechanism="self",
        amount=5, type="Interest", idempotency_suffix="wrong-mechanism-interest-legacy",
    )

    seat_ids = get_seat_ids_with_student_originated_activity(
        classroom.class_id, WINDOW_START, WINDOW_END
    )
    assert seat_id not in seat_ids
    ids = get_student_originated_transaction_ids(classroom.class_id, [txn.id])
    assert ids == set()


def test_null_type_row_counts_as_student_originated(client, app):
    """A legacy row with no ``type`` at all must not be excluded -- ``NULL
    NOT IN (...)`` is unknown in SQL, so the filter explicitly treats NULL as
    passing, matching mechanism as the load-bearing clause (§6.6)."""
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat_id = classroom.students[0].seat_id
    txn = _row(
        classroom, feat_name="FEAT-OBL-001", mechanism="self",
        amount=5, type=None, idempotency_suffix="null-type",
    )

    seat_ids = get_seat_ids_with_student_originated_activity(
        classroom.class_id, WINDOW_START, WINDOW_END
    )
    assert seat_id in seat_ids
    ids = get_student_originated_transaction_ids(classroom.class_id, [txn.id])
    assert txn.id in ids


# --- Cross-class isolation ---------------------------------------------------


def test_student_originated_activity_scoped_by_class(client, app):
    first = provision_ledger_classroom("chemistry_p1", app)
    second = provision_ledger_classroom("ap_csp_p3", app)
    first_seat_id = first.students[0].seat_id
    second_seat_id = second.students[0].seat_id

    _row(
        first, feat_name="FEAT-OBL-003", amount=-5,
        type="insurance_premium", idempotency_suffix="first-class",
    )

    seat_ids = get_seat_ids_with_student_originated_activity(
        first.class_id, WINDOW_START, WINDOW_END
    )
    assert first_seat_id in seat_ids
    assert second_seat_id not in seat_ids

    other_class_seat_ids = get_seat_ids_with_student_originated_activity(
        second.class_id, WINDOW_START, WINDOW_END
    )
    assert other_class_seat_ids == set()
