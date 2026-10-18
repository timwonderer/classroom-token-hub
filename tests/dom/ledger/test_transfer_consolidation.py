"""build_transfer_effect_pair is the one Ledger-owned constructor for the
two-leg transfer effect vector (DOM-LED-001 INV-LED-014). Both the standalone
internal-transfer route (create_transfer_pair) and the overdraft-protection
funding legs inside apply_resolved_ledger_plan compose it; these tests pin the
builder's own validation and the standalone path's idempotency/replay/scoping
behavior under the new composition onto create_reserved_effects."""

from decimal import Decimal

import pytest

from app.feats.base import FEATContext
from app.models import LedgerCommandReservation, Transaction
from app.services.ledger_transfer_service import (
    build_transfer_effect_pair,
    create_transfer_pair,
)
from tests.helpers.ledger import provision_ledger_classroom, create_ledger_idempotent_transaction


def test_build_transfer_effect_pair_returns_exact_two_leg_vector():
    effects = build_transfer_effect_pair(
        seat_id=42, class_id="class-1", mechanism="self",
        amount=Decimal("12.345"), from_account="checking", to_account="savings",
        withdraw_description="out", deposit_description="in",
    )
    assert len(effects) == 2
    debit, credit = effects
    assert debit["seat_id"] == credit["seat_id"] == 42
    assert debit["target_seat_id"] == credit["target_seat_id"] == 42
    assert debit["actor_seat_id"] == credit["actor_seat_id"] == 42
    assert debit["mechanism"] == credit["mechanism"] == "self"
    assert debit["account_type"] == "checking"
    assert credit["account_type"] == "savings"
    assert debit["type"] == "Withdrawal"
    assert credit["type"] == "Deposit"
    assert debit["amount"] == -Decimal("12.34")  # quantized (ROUND_HALF_EVEN)
    assert credit["amount"] == Decimal("12.34")
    assert debit["description"] == "out"
    assert credit["description"] == "in"


def test_build_transfer_effect_pair_honors_distinct_actor_and_target():
    """The overdraft-funding call site attributes legs to the plan's own actor,
    not the transferring seat, while both legs still move that seat's money."""
    effects = build_transfer_effect_pair(
        seat_id=7, class_id="class-1", target_seat_id=7, actor_seat_id=99,
        mechanism="teacher", correlation_id="corr_funding_abc",
        amount=Decimal("5.00"), from_account="savings", to_account="checking",
        withdraw_description="to checking", deposit_description="from savings",
    )
    assert all(e["seat_id"] == 7 and e["target_seat_id"] == 7 for e in effects)
    assert all(e["actor_seat_id"] == 99 for e in effects)
    assert all(e["mechanism"] == "teacher" for e in effects)
    assert all(e["correlation_id"] == "corr_funding_abc" for e in effects)


@pytest.mark.parametrize(
    "from_account,to_account,amount",
    [
        ("checking", "checking", Decimal("1.00")),  # same account
        ("checking", "savings", Decimal("0.00")),  # zero amount
        ("checking", "savings", Decimal("-5.00")),  # negative amount
        ("checking", "wallet", Decimal("1.00")),  # non-canonical account
    ],
)
def test_build_transfer_effect_pair_rejects_invalid_input(from_account, to_account, amount):
    with pytest.raises(ValueError):
        build_transfer_effect_pair(
            seat_id=1, class_id="class-1", amount=amount,
            from_account=from_account, to_account=to_account,
            withdraw_description="out", deposit_description="in",
        )


def test_create_transfer_pair_idempotent_replay_returns_same_two_effects(app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat_id = classroom.students[0].seat.id
    class_id = classroom.class_id
    with FEATContext("FEAT-LED-001", idempotency_key="transfer:seed"):
        create_ledger_idempotent_transaction(
            idempotency_key=f"fund:{seat_id}", seat_id=seat_id, class_id=class_id,
            amount=Decimal("50.00"), account_type="checking", type="payroll",
            description="seed",
        )
    with FEATContext("FEAT-LED-000", idempotency_key="transfer:replay-test"):
        first_debit, first_credit = create_transfer_pair(
            seat_id=seat_id, class_id=class_id, amount=Decimal("10.00"),
            from_account="checking", to_account="savings",
            withdraw_description="Transfer", deposit_description="Transfer",
        )
        second_debit, second_credit = create_transfer_pair(
            seat_id=seat_id, class_id=class_id, amount=Decimal("10.00"),
            from_account="checking", to_account="savings",
            withdraw_description="Transfer", deposit_description="Transfer",
        )
    assert second_debit.id == first_debit.id
    assert second_credit.id == first_credit.id
    reservation_id = first_debit.command_reservation_id
    assert first_credit.command_reservation_id == reservation_id
    assert Transaction.query.filter_by(command_reservation_id=reservation_id).count() == 2


def test_create_transfer_pair_replay_mismatch_raises(app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat_id = classroom.students[0].seat.id
    class_id = classroom.class_id
    with FEATContext("FEAT-LED-001", idempotency_key="transfer:seed2"):
        create_ledger_idempotent_transaction(
            idempotency_key=f"fund2:{seat_id}", seat_id=seat_id, class_id=class_id,
            amount=Decimal("50.00"), account_type="checking", type="payroll",
            description="seed",
        )
    with FEATContext("FEAT-LED-000", idempotency_key="transfer:mismatch-test"):
        create_transfer_pair(
            seat_id=seat_id, class_id=class_id, amount=Decimal("10.00"),
            from_account="checking", to_account="savings",
            withdraw_description="Transfer", deposit_description="Transfer",
        )
        with pytest.raises(ValueError, match="Replay fingerprint mismatch"):
            # Same reservation key, different amount: must not silently replay
            # the original two effects under a changed request.
            create_transfer_pair(
                seat_id=seat_id, class_id=class_id, amount=Decimal("20.00"),
                from_account="checking", to_account="savings",
                withdraw_description="Transfer", deposit_description="Transfer",
            )


def test_create_transfer_pair_scoped_by_class_not_shared_across_classes(app):
    """Two classes using the identical idempotency key must not cross-replay
    each other's reservation (class_id is the isolation key, not the key alone)."""
    first = provision_ledger_classroom("chemistry_p1", app)
    second = provision_ledger_classroom("ap_csp_p3", app)
    first_seat = first.students[0].seat.id
    second_seat = second.students[0].seat.id
    for classroom, seat_id in ((first, first_seat), (second, second_seat)):
        with FEATContext("FEAT-LED-001", idempotency_key=f"transfer:seed-{classroom.class_id}"):
            create_ledger_idempotent_transaction(
                idempotency_key=f"fund-x:{seat_id}", seat_id=seat_id, class_id=classroom.class_id,
                amount=Decimal("50.00"), account_type="checking", type="payroll",
                description="seed",
            )
    shared_key = "transfer:shared-key-across-classes"
    with FEATContext("FEAT-LED-000", idempotency_key=shared_key):
        first_debit, first_credit = create_transfer_pair(
            seat_id=first_seat, class_id=first.class_id, amount=Decimal("10.00"),
            from_account="checking", to_account="savings",
            withdraw_description="Transfer", deposit_description="Transfer",
        )
        second_debit, second_credit = create_transfer_pair(
            seat_id=second_seat, class_id=second.class_id, amount=Decimal("10.00"),
            from_account="checking", to_account="savings",
            withdraw_description="Transfer", deposit_description="Transfer",
        )
    assert first_debit.id != second_debit.id
    assert first_debit.class_id == first.class_id
    assert second_debit.class_id == second.class_id
    first_reservation = first_debit.command_reservation_id
    second_reservation = second_debit.command_reservation_id
    assert first_reservation != second_reservation
    assert LedgerCommandReservation.query.filter_by(
        id=first_reservation, class_id=first.class_id
    ).one_or_none() is not None
    assert LedgerCommandReservation.query.filter_by(
        id=second_reservation, class_id=second.class_id
    ).one_or_none() is not None
