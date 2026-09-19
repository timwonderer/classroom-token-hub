from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Transaction
from app.services import ledger_command_service
from app.services.ledger_command_service import _replay_fingerprint, create_reserved_effects
from app.utils.transaction_idempotency import (
    IDEMPOTENT_TRANSACTION_TYPES,
    MAX_IDEMPOTENCY_KEY_LENGTH,
    _command_fingerprint,
    insurance_reimbursement_key,
)
from app.feats.base import FEATContext
from tests.helpers.ledger import (
    create_ledger_idempotent_transaction,
    create_ledger_pending_transaction,
    provision_ledger_classroom,
)


def test_DOM_LED_001__idempotent_transaction_types_are_explicit():
    expected = frozenset({
        # The canonical compensating type (FEAT-LED-002 §III.2.1). A reversal
        # persists this in `type`; the business reason it was raised for lives in
        # Transaction.compensation_subtype, so `issue_reversal`,
        # `issue_compensation` and `refund` stay listed for the rows written
        # before that split.
        "REVERSAL",
        "insurance_reimbursement",
        "insurance_premium",
        "purchase",
        "refund",
        "overdraft_fee",
        "payroll",
        "manual_payment",
        "bug_reward",
        "issue_reversal",
        "issue_compensation",
        # Added by the canonical rent obligation model (564fa49a) without
        # updating this pin. A rent charge must not double-post on retry, so it
        # belongs in the set; the enumeration here is what had gone stale.
        "rent_payment",
        "Interest",
        "void_item_removed",
    })
    assert IDEMPOTENT_TRANSACTION_TYPES == expected


def test_DOM_LED_001__one_to_many_reservation_replays_effect_set(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    first = classroom.students[0].seat
    second = classroom.students[1].seat
    effects = [
        {"seat_id": first.id, "class_id": classroom.class_id, "target_seat_id": first.id,
         "actor_seat_id": classroom.teacher_seat.id, "mechanism": "teacher",
         "amount": Decimal("2.00"), "account_type": "checking",
         "type": "manual_payment", "description": "bonus"},
        {"seat_id": second.id, "class_id": classroom.class_id, "target_seat_id": second.id,
         "actor_seat_id": classroom.teacher_seat.id, "mechanism": "teacher",
         "amount": Decimal("2.00"), "account_type": "checking",
         "type": "manual_payment", "description": "bonus"},
    ]
    with FEATContext("FEAT-LED-000", idempotency_key="command:bulk-replay"):
        created, was_created = create_reserved_effects(
            class_id=classroom.class_id, feat_code="FEAT-LED-000",
            idempotency_key="command:bulk-replay", effects=effects,
        )
        replay, replay_created = create_reserved_effects(
            class_id=classroom.class_id, feat_code="FEAT-LED-000",
            idempotency_key="command:bulk-replay", effects=effects,
        )
    assert was_created is True
    assert replay_created is False
    assert [tx.id for tx in replay] == [tx.id for tx in created]

    changed = [dict(effect) for effect in effects]
    with FEATContext("FEAT-LED-000", idempotency_key="command:bulk-replay-mismatch"):
        create_reserved_effects(
            class_id=classroom.class_id, feat_code="FEAT-LED-000",
            idempotency_key="command:bulk-replay-mismatch", effects=effects,
        )
        changed[0]["amount"] = Decimal("4.00")
        with pytest.raises(ValueError, match="Replay fingerprint mismatch"):
            create_reserved_effects(
                class_id=classroom.class_id, feat_code="FEAT-LED-000",
                idempotency_key="command:bulk-replay-mismatch", effects=changed,
            )


def test_DOM_LED_001__idempotent_transaction_reuses_existing_row_on_retry(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    class_row = classroom.economy
    student = classroom.students[0].seat
    db.session.commit()

    idempotency_key = insurance_reimbursement_key(123)
    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_reuse_1"):
        transaction_one, created_one = create_ledger_idempotent_transaction(
            idempotency_key=idempotency_key,
            seat_id=student.id,
            class_id=class_row.class_id,

            amount=Decimal("10.00"),
            account_type="checking",
            type="insurance_reimbursement",
            description="Insurance reimbursement",
        )
    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_reuse_2"):
        transaction_two, created_two = create_ledger_idempotent_transaction(
            idempotency_key=idempotency_key,
            seat_id=student.id,
            class_id=class_row.class_id,

            amount=Decimal("10.00"),
            account_type="checking",
            type="insurance_reimbursement",
            description="Insurance reimbursement",
        )

    assert created_one is True
    assert created_two is False
    assert transaction_one.id == transaction_two.id
    assert Transaction.query.filter_by(idempotency_key=idempotency_key).count() == 1


def test_DOM_LED_001__idempotent_transaction_recovers_from_integrity_race(client, monkeypatch, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    class_row = classroom.economy
    student = classroom.students[0].seat
    db.session.commit()

    idempotency_key = insurance_reimbursement_key(456)
    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_race_seed"):
        winning_tx, winning_created = create_ledger_idempotent_transaction(
            idempotency_key=idempotency_key,
            seat_id=student.id,
            class_id=class_row.class_id,

            amount=Decimal("11.00"),
            account_type="checking",
            type="insurance_reimbursement",
            description="Winning insurance reimbursement",
        )
        assert winning_created is True

    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_race_call"):
        transaction, created = create_ledger_idempotent_transaction(
            idempotency_key=idempotency_key,
            seat_id=student.id,
            class_id=class_row.class_id,

            amount=Decimal("11.00"),
            account_type="checking",
            type="insurance_reimbursement",
            description="Losing insurance reimbursement",
        )

    assert created is False
    assert transaction is not None
    assert transaction.id == winning_tx.id
    assert transaction.idempotency_key == idempotency_key
    assert Transaction.query.filter_by(idempotency_key=idempotency_key).count() == 1


def test_DOM_LED_001__idempotent_transaction_rejects_non_idempotent_types(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    class_row = classroom.economy
    student = classroom.students[0].seat
    db.session.commit()

    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_reject_type"):
        with pytest.raises(ValueError):
            create_ledger_idempotent_transaction(
                idempotency_key="txn:unknown:op",
                seat_id=student.id,
                class_id=class_row.class_id,

                amount=Decimal("5.00"),
                account_type="checking",
                type="UnknownType",
                description="Should fail",
            )


@pytest.mark.parametrize("bad_key", [None, "", "   "])
def test_DOM_LED_001__idempotent_transaction_rejects_empty_keys(client, bad_key, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    class_row = classroom.economy
    student = classroom.students[0].seat
    db.session.commit()

    with FEATContext("FEAT-LED-000", idempotency_key=f"test_transaction_idempotency_empty_{bad_key!s}"):
        with pytest.raises(ValueError):
            create_ledger_idempotent_transaction(
                idempotency_key=bad_key,
                seat_id=student.id,
                class_id=class_row.class_id,

                amount=Decimal("5.00"),
                account_type="checking",
                type="refund",
                description="Should fail",
            )


def test_DOM_LED_001__idempotent_transaction_rejects_oversize_keys(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    class_row = classroom.economy
    student = classroom.students[0].seat
    db.session.commit()

    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_oversize"):
        with pytest.raises(ValueError):
            create_ledger_idempotent_transaction(
                idempotency_key="x" * (MAX_IDEMPOTENCY_KEY_LENGTH + 1),
                seat_id=student.id,
                class_id=class_row.class_id,

                amount=Decimal("5.00"),
                account_type="checking",
                type="refund",
                description="Should fail",
            )


# Digests produced by the version 1 serializer as it stood on main before
# correlation_id was folded into it. They pin SPEC-LED-002 §4.2: a later
# serializer change must not silently rehash what an earlier version accepted.
_V1_REIMBURSEMENT_DIGEST = "fc4f30178cbd882a3c2e7459c505f46508ea56971a36fe7f6407936dff578426"
_V1_INTEREST_DIGEST = "cf344c13e159fa619928b2bd5bb27155b8f6cc334f841b4b099e697af71518de"
_V1_BULK_DIGEST = "e00d871d802ad24c012b42a79cb8da122b301b595fb241b49c8a0b9b8254b85a"


def _single(type_, amount, account_type="checking"):
    return dict(
        target_seat_id=7, actor_seat_id=7, amount=amount, account_type=account_type,
        type=type_, original_transaction_id=None, policy_id=None,
    )


def _bulk_effects():
    return [
        {"seat_id": 7, "class_id": "c", "target_seat_id": 7, "actor_seat_id": 3,
         "mechanism": "teacher", "amount": Decimal("2.00"),
         "account_type": "checking", "type": "manual_payment", "description": "bonus"},
        {"seat_id": 8, "class_id": "c", "target_seat_id": 8, "actor_seat_id": 3,
         "mechanism": "teacher", "amount": Decimal("2.00"),
         "account_type": "checking", "type": "manual_payment", "description": "bonus"},
    ]


def test_SPEC_LED_002__version_one_digests_are_unchanged():
    assert _command_fingerprint(**_single("insurance_reimbursement", Decimal("10.00")), version=1) == _V1_REIMBURSEMENT_DIGEST
    assert _command_fingerprint(**_single("Interest", Decimal("1.25"), "savings"), version=1) == _V1_INTEREST_DIGEST
    with pytest.raises(ValueError, match="Legacy multi-effect"):
        _replay_fingerprint(_bulk_effects(), 1)


def test_SPEC_LED_002__version_two_changes_only_the_interest_amount():
    assert _command_fingerprint(**_single("insurance_reimbursement", Decimal("10.00")), version=2) == _V1_REIMBURSEMENT_DIGEST
    with pytest.raises(ValueError, match="Legacy multi-effect"):
        _replay_fingerprint(_bulk_effects(), 2)

    first = _command_fingerprint(**_single("Interest", Decimal("1.25"), "savings"), version=2)
    recomputed = _command_fingerprint(**_single("Interest", Decimal("1.31"), "savings"), version=2)
    assert first == recomputed
    assert first != _V1_INTEREST_DIGEST


def test_SPEC_LED_002__correlation_id_is_not_part_of_the_fingerprint():
    effect = _bulk_effects()[0]
    correlated = {**effect, "correlation_id": "purchase-correlation"}
    assert _replay_fingerprint([correlated], 2) == _replay_fingerprint([effect], 2)
    assert _replay_fingerprint([correlated, _bulk_effects()[1]], 3) == _replay_fingerprint(_bulk_effects(), 3)


def _interest_effect(classroom, seat, amount, account_type="savings"):
    return {
        "seat_id": seat.id, "class_id": classroom.class_id, "target_seat_id": seat.id,
        "actor_seat_id": seat.id, "mechanism": "self",
        "amount": amount, "account_type": account_type, "type": "Interest",
        "description": "Monthly Savings Interest",
    }


def test_SPEC_LED_002__interest_replays_across_a_recomputed_amount(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    key = "savings-interest:recomputed"
    with FEATContext("FEAT-LED-000", idempotency_key=key):
        created, was_created = create_reserved_effects(
            class_id=classroom.class_id, feat_code="FEAT-LED-000", idempotency_key=key,
            effects=[_interest_effect(classroom, seat, Decimal("1.25"))],
        )
        replay, replay_created = create_reserved_effects(
            class_id=classroom.class_id, feat_code="FEAT-LED-000", idempotency_key=key,
            effects=[_interest_effect(classroom, seat, Decimal("1.31"))],
        )
    assert was_created is True
    assert replay_created is False
    assert [tx.id for tx in replay] == [tx.id for tx in created]
    assert replay[0].amount == Decimal("1.25")


@pytest.mark.parametrize("collision", ["other_seat", "other_account"])
def test_SPEC_LED_002__interest_key_reuse_fails_closed(client, app, collision):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    first = classroom.students[0].seat
    second = classroom.students[1].seat
    key = f"savings-interest:collision:{collision}"
    colliding = (
        _interest_effect(classroom, second, Decimal("1.25"))
        if collision == "other_seat"
        else _interest_effect(classroom, first, Decimal("1.25"), account_type="checking")
    )
    with FEATContext("FEAT-LED-000", idempotency_key=key):
        create_reserved_effects(
            class_id=classroom.class_id, feat_code="FEAT-LED-000", idempotency_key=key,
            effects=[_interest_effect(classroom, first, Decimal("1.25"))],
        )
        with pytest.raises(ValueError, match="Replay fingerprint mismatch"):
            create_reserved_effects(
                class_id=classroom.class_id, feat_code="FEAT-LED-000", idempotency_key=key,
                effects=[colliding],
            )


def test_SPEC_LED_002__version_one_reservation_is_compared_under_version_one(client, app, monkeypatch):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    effect = {
        "seat_id": seat.id, "class_id": classroom.class_id, "target_seat_id": seat.id,
        "actor_seat_id": classroom.teacher_seat.id, "mechanism": "teacher",
        "amount": Decimal("3.00"), "account_type": "checking",
        "type": "manual_payment", "description": "bonus",
    }
    key = "command:accepted-under-v1"
    with FEATContext("FEAT-LED-000", idempotency_key=key):
        monkeypatch.setattr(ledger_command_service, "FINGERPRINT_VERSION", 1)
        created, _ = create_reserved_effects(
            class_id=classroom.class_id, feat_code="FEAT-LED-000", idempotency_key=key,
            effects=[effect],
        )
        monkeypatch.undo()
        assert created[0].command_reservation.fingerprint_version == 1

        replay, replay_created = create_reserved_effects(
            class_id=classroom.class_id, feat_code="FEAT-LED-000", idempotency_key=key,
            effects=[effect],
        )
        assert replay_created is False
        assert [tx.id for tx in replay] == [tx.id for tx in created]

        with pytest.raises(ValueError, match="Replay fingerprint mismatch"):
            create_reserved_effects(
                class_id=classroom.class_id, feat_code="FEAT-LED-000", idempotency_key=key,
                effects=[{**effect, "amount": Decimal("4.00")}],
            )
