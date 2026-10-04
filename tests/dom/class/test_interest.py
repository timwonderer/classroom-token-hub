from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app import Transaction, db
from app.feats.base import FEATContext
from unittest.mock import patch
from tests.helpers.classroom_initializer import initialize


def test_DOM_CLASS_001__apply_savings_interest_with_canonical_historical_admission(client, app):
    classroom = initialize("chemistry_p1", app)
    test_student = classroom.students[0].seat
    past_date = datetime.now(timezone.utc) - timedelta(days=31)
    from tests.helpers.ledger import record_ledger_fixture
    with FEATContext("FEAT-LED-001", idempotency_key="interest:test_apply_savings_interest"):
        record_ledger_fixture(
            seat_id=test_student.id, class_id=test_student.class_id,
            amount=Decimal("100.00"), account_type="savings",
            description="Initial savings deposit", timestamp=past_date,
            posted=True,
        )

    with patch("app.routes.student.resolve_canonical_context", return_value=type("Ctx", (), {"class_id": test_student.class_id})()), patch("app.routes.student.get_current_seat", return_value=test_student):
        from app.services.ledger_interest_service import (
            apply_savings_interest,
            payout_window_containing,
        )
        window = payout_window_containing(
            test_student.class_id, "monthly", datetime.now(timezone.utc)
        )
        with FEATContext("FEAT-LED-001", idempotency_key="interest:test_apply_savings_interest_run"):
            # The rate is a Class-Config policy input and this classroom configures
            # none. SPEC-ECON-001 §11 forbids a hidden default APY, so an
            # unconfigured class pays nothing. Supply the rate explicitly — the
            # documented deterministic-replay override — because what this test
            # pins is historical admission and daily accrual, not rate resolution. The payout
            # window (monthly, the unconfigured default) must have closed, so the
            # evaluation instant is taken just past the end of the current month.
            apply_savings_interest(
                test_student,
                annual_rate=Decimal("0.045"),
                reference_time_utc=window.end_utc + timedelta(hours=1),
            )

    interest_tx = (
        Transaction.query.filter_by(
            seat_id=test_student.id,
            class_id=test_student.class_id,
            description="Monthly Savings Interest",
            account_type='savings',
        )
        .order_by(Transaction.id.desc())
        .first()
    )

    assert interest_tx is not None
    # Daily balance method (SPEC-ECON-001 §9.2): 100 held all month, simple
    # interest, 0.045 / 365 a day, rounded once. The seat was claimed today, and
    # days before the claim accrue nothing (§8.2), so the days run from today
    # through the month's end.
    from app.utils.canonical_temporal_resolver import (
        CLASS_LEVEL_EVALUATION,
        canonical_temporal_resolver,
    )
    claim_day = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=type("Ctx", (), {"class_id": test_student.class_id})(),
        primitive="evaluation_day_boundaries",
        reference_time_utc=test_student.claimed_at,
    )
    days = round((window.end_utc - claim_day.boundary_start_utc).total_seconds() / 86400)
    expected = (Decimal("100") * Decimal("0.045") / 365 * days).quantize(Decimal("0.01"))
    assert interest_tx.amount == expected
