"""Shared funding stays atomic, whole-shortfall and reservation-owned."""

from decimal import Decimal
from dataclasses import replace
import pytest
from app.extensions import db
from app.feats.base import FEATContext
from app.models import Transaction
from app.services.class_configuration_query_service import get_banking_directive
from app.services.ledger_resolution_service import (
    build_intended_ledger_plan,
    resolve_intended_ledger_plan,
    apply_resolved_ledger_plan,
)
from app.services.ledger_balance_query_service import get_available_balances
from app.services.ledger_command_service import replay_reserved_charge
from tests.helpers.ledger import provision_ledger_classroom, record_ledger_fixture


@pytest.mark.parametrize(
    "savings,enabled,checking_after,savings_after,legs",
    [
        ("3.00", True, "-8.00", "3.00", 1),
        ("8.00", True, "0.00", "0.00", 3),
        ("20.00", False, "-8.00", "20.00", 1),
    ],
)
def test_whole_shortfall_and_reservation_replay(
    app, savings, enabled, checking_after, savings_after, legs
):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat_id = classroom.students[0].seat.id
    class_id = classroom.class_id
    with FEATContext("FEAT-LED-001", idempotency_key="funding:seed"):
        record_ledger_fixture(
            seat_id=seat_id, class_id=class_id, amount=Decimal("2.00")
        )
        record_ledger_fixture(
            seat_id=seat_id,
            class_id=class_id,
            amount=Decimal(savings),
            account_type="savings",
        )
    db.session.commit()
    directive = replace(get_banking_directive(class_id), protection_enabled=enabled)
    intent = ("TEST_CHARGE", "10.00")
    with FEATContext("FEAT-LED-001", idempotency_key="funding:charge"):
        plan = build_intended_ledger_plan(
            seat_id=seat_id,
            class_id=class_id,
            actor_seat_id=seat_id,
            target_seat_id=seat_id,
            mechanism="self",
            debit_amount=Decimal("10.00"),
            description="Authorized charge",
            transaction_type="purchase",
            canonical_intent=intent,
        )
        resolved = resolve_intended_ledger_plan(plan=plan, banking_directive=directive)
        result = apply_resolved_ledger_plan(
            resolved_plan=resolved, idempotency_key="funding:charge"
        )
    db.session.commit()
    balances = get_available_balances(seat_id, class_id)
    assert balances[0] == Decimal(checking_after)
    assert balances[1] == Decimal(savings_after)
    assert len(result["effects"]) == legs
    assert len({row.command_reservation_id for row in result["effects"]}) == 1
    assert all(row.compensation_amount_cents == 0 for row in result["effects"])
    if legs == 3:
        funding = result["effects"][:2]
        assert funding[0].correlation_id == funding[1].correlation_id
        assert funding[0].correlation_id != result["principal"].correlation_id
        assert sum(row.amount_cents for row in funding) == 0
        assert (
            Transaction.query.filter_by(
                class_id=class_id, correlation_id=funding[0].correlation_id
            ).count()
            == 2
        )
    with FEATContext("FEAT-LED-001", idempotency_key="funding:charge"):
        replay = replay_reserved_charge(
            class_id=class_id,
            feat_code="FEAT-LED-001",
            idempotency_key="funding:charge",
            seat_id=seat_id,
            actor_seat_id=seat_id,
            principal_type="purchase",
            canonical_intent=intent,
        )
        assert replay["principal"].id == result["principal"].id
        with pytest.raises(ValueError, match="fingerprint"):
            replay_reserved_charge(
                class_id=class_id,
                feat_code="FEAT-LED-001",
                idempotency_key="funding:charge",
                seat_id=seat_id,
                actor_seat_id=seat_id,
                principal_type="purchase",
                canonical_intent=("TEST_CHARGE", "11.00"),
            )


def test_stale_funding_plan_fails_before_effect_creation(app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat_id = classroom.students[0].seat.id
    class_id = classroom.class_id
    with FEATContext("FEAT-LED-001", idempotency_key="stale:seed"):
        record_ledger_fixture(
            seat_id=seat_id, class_id=class_id, amount=Decimal("2.00")
        )
    db.session.commit()
    with FEATContext("FEAT-LED-001", idempotency_key="stale:charge"):
        plan = build_intended_ledger_plan(
            seat_id=seat_id,
            class_id=class_id,
            actor_seat_id=seat_id,
            target_seat_id=seat_id,
            mechanism="self",
            debit_amount=Decimal("10.00"),
            description="Charge",
            transaction_type="purchase",
        )
        resolved = resolve_intended_ledger_plan(
            plan=plan, banking_directive=get_banking_directive(class_id)
        )
        record_ledger_fixture(
            seat_id=seat_id, class_id=class_id, amount=Decimal("-1.00")
        )
        before = Transaction.query.count()
        with pytest.raises(ValueError, match="PREVIEW_CHANGED"):
            apply_resolved_ledger_plan(
                resolved_plan=resolved, idempotency_key="stale:charge"
            )
        assert Transaction.query.count() == before


def test_unrelated_mixed_correlation_remains_denied(app):
    from app.services.ledger_posting_service import create_pending_transaction

    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat_id = classroom.students[0].seat.id
    with pytest.raises(ValueError, match="Mixed correlation"):
        with FEATContext("FEAT-LED-001", idempotency_key="mixed:bad"):
            create_pending_transaction(
                seat_id=seat_id,
                class_id=classroom.class_id,
                actor_seat_id=seat_id,
                target_seat_id=seat_id,
                mechanism="self",
                amount=Decimal("1.00"),
                account_type="checking",
                type="Deposit",
                description="Unrelated correlation",
                correlation_id="corr_unrelated",
            )
    db.session.rollback()


def test_partial_funding_creation_rolls_back_reservation_and_all_legs(app, monkeypatch):
    from app.models import LedgerCommandReservation
    import app.services.ledger_posting_service as posting

    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat_id = classroom.students[0].seat.id
    class_id = classroom.class_id
    with FEATContext("FEAT-LED-001", idempotency_key="fault:seed"):
        record_ledger_fixture(
            seat_id=seat_id, class_id=class_id, amount=Decimal("2.00")
        )
        record_ledger_fixture(
            seat_id=seat_id,
            class_id=class_id,
            amount=Decimal("8.00"),
            account_type="savings",
        )
    db.session.commit()
    before = Transaction.query.count()
    balances = get_available_balances(seat_id, class_id)
    original_emit = posting.audit_protected
    count = 0

    def fail_second_effect(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("injected funding audit failure")
        return original_emit(*args, **kwargs)

    monkeypatch.setattr(posting, "audit_protected", fail_second_effect)
    with pytest.raises(RuntimeError, match="injected funding"):
        with FEATContext("FEAT-LED-001", idempotency_key="fault:charge"):
            plan = build_intended_ledger_plan(
                seat_id=seat_id,
                class_id=class_id,
                actor_seat_id=seat_id,
                target_seat_id=seat_id,
                mechanism="self",
                debit_amount=Decimal("10.00"),
                description="Charge",
                transaction_type="purchase",
            )
            directive = replace(
                get_banking_directive(class_id), protection_enabled=True
            )
            resolved = resolve_intended_ledger_plan(
                plan=plan, banking_directive=directive
            )
            apply_resolved_ledger_plan(
                resolved_plan=resolved, idempotency_key="fault:charge"
            )
    db.session.rollback()
    assert Transaction.query.count() == before
    assert get_available_balances(seat_id, class_id) == balances
    assert (
        LedgerCommandReservation.query.filter_by(
            class_id=class_id, idempotency_key="fault:charge"
        ).first()
        is None
    )


