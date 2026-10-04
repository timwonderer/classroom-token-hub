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


def test_funded_explicit_fee_replay_does_not_reprice_or_charge_twice(app):
    from app.services.ledger_fee_service import apply_overdraft_fee_if_needed
    from app.models import Seat

    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = db.session.get(Seat, classroom.students[0].seat.id)
    with FEATContext("FEAT-LED-001", idempotency_key="fee:seed"):
        record_ledger_fixture(
            seat_id=seat.id, class_id=seat.class_id, amount=Decimal("2.00")
        )
        record_ledger_fixture(
            seat_id=seat.id,
            class_id=seat.class_id,
            amount=Decimal("30.00"),
            account_type="savings",
        )
    db.session.commit()
    directive = replace(
        get_banking_directive(seat.class_id),
        protection_enabled=True,
        flat_fee=Decimal("10.00"),
    )
    with FEATContext("FEAT-LED-001", idempotency_key="fee:charge"):
        accepted, amount = apply_overdraft_fee_if_needed(
            seat,
            banking_directive=directive,
            actor_seat_id=classroom.teacher_seat_id,
            force=True,
            idempotency_key="fee:charge",
        )
        assert accepted and amount == Decimal("10.00")
    db.session.commit()
    before = get_available_balances(seat.id, seat.class_id)
    ids = [
        row.id
        for row in Transaction.query.filter_by(idempotency_key="fee:charge").all()
    ]
    assert len(ids) == 3
    with FEATContext("FEAT-LED-001", idempotency_key="fee:charge"):
        accepted, amount = apply_overdraft_fee_if_needed(
            seat,
            banking_directive=replace(directive, flat_fee=Decimal("20.00")),
            actor_seat_id=classroom.teacher_seat_id,
            force=True,
            idempotency_key="fee:charge",
        )
        assert accepted and amount == Decimal("10.00")
        with pytest.raises(ValueError, match="fingerprint"):
            apply_overdraft_fee_if_needed(
                seat,
                banking_directive=directive,
                actor_seat_id=classroom.teacher_seat_id,
                force=False,
                idempotency_key="fee:charge",
            )
    assert get_available_balances(seat.id, seat.class_id) == before
    assert [
        row.id
        for row in Transaction.query.filter_by(idempotency_key="fee:charge").all()
    ] == ids


@pytest.mark.parametrize(
    "fee_inputs",
    [
        {"flat_fee": Decimal("-1.00")},
        {"flat_fee": Decimal("NaN")},
        {"flat_fee": None, "progressive_fee": (("tier_1", "10%"),), "cwi": None},
    ],
)
def test_malformed_applicable_fee_inputs_fail_closed(app, fee_inputs):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat_id = classroom.students[0].seat.id
    directive = replace(get_banking_directive(classroom.class_id), **fee_inputs)
    plan = build_intended_ledger_plan(
        seat_id=seat_id,
        class_id=classroom.class_id,
        actor_seat_id=classroom.teacher_seat_id,
        target_seat_id=seat_id,
        mechanism="system",
        debit_amount=Decimal("0.00"),
        description="Fee",
        transaction_type="overdraft_fee",
        fee_actor_seat_id=classroom.teacher_seat_id,
    )
    with pytest.raises(ValueError, match="banking fee directive"):
        resolve_intended_ledger_plan(
            plan=plan,
            banking_directive=directive,
            fee_authority="EXPLICIT_FEE",
            force_overdraft_fee=True,
        )
    assert Transaction.query.filter_by(class_id=classroom.class_id).count() == 0


@pytest.mark.parametrize(
    "fee_inputs",
    [
        {"flat_fee": Decimal("-1.00")},
        {"flat_fee": Decimal("NaN")},
        {"flat_fee": Decimal("Infinity")},
        {"flat_fee": None, "progressive_fee": None, "cwi": None},
    ],
)
def test_irrelevant_malformed_fee_inputs_do_not_block_funded_or_no_fee_charge(
    app, fee_inputs
):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat_id = classroom.students[0].seat.id
    with FEATContext("FEAT-LED-001", idempotency_key="irrelevant-fee:seed"):
        record_ledger_fixture(
            seat_id=seat_id, class_id=classroom.class_id, amount=Decimal("20.00")
        )
    db.session.commit()
    directive = replace(get_banking_directive(classroom.class_id), **fee_inputs)
    plan = build_intended_ledger_plan(
        seat_id=seat_id,
        class_id=classroom.class_id,
        actor_seat_id=seat_id,
        target_seat_id=seat_id,
        mechanism="self",
        debit_amount=Decimal("10.00"),
        description="Charge",
        transaction_type="purchase",
    )
    for authority in ("NONE", "FAILED_AGREEMENT"):
        resolved = resolve_intended_ledger_plan(
            plan=plan, banking_directive=directive, fee_authority=authority
        )
        assert resolved.checking_after == Decimal("10.00")
        assert resolved.overdraft_fee_amount == Decimal("0.00")
