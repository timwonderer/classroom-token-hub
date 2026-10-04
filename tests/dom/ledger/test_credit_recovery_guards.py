"""Recovery requires strict evidence, counts pending effects and caps principal."""

from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError, DBAPIError
from app.extensions import db
from app.feats.base import FEATContext
from app.feats.ledger_proof_inputs import positive_reversal_inputs
from app.services.ledger_recovery_service import (
    ledger_origin_locator,
    get_credit_compensation_proof,
    resolve_credit_recovery,
    apply_credit_recovery,
    RecoveryIntegrityError,
)
from app.services.ledger_balance_query_service import get_account_posting_boundary
from app.services.ledger_posting_service import create_pending_transaction
from tests.helpers.ledger import provision_ledger_classroom, record_ledger_fixture


def _original(app, *, posted=True, account_type="checking"):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    with FEATContext("FEAT-LED-001", idempotency_key="cap:seed"):
        original = record_ledger_fixture(
            seat_id=classroom.students[0].seat.id,
            class_id=classroom.class_id,
            actor_seat_id=classroom.teacher_seat_id,
            target_seat_id=classroom.students[0].seat.id,
            mechanism="teacher",
            amount=Decimal("10.00"),
            type="payroll",
            account_type=account_type,
            posted=posted,
        )
    db.session.commit()
    return classroom, original


def _proof(original, inputs):
    return get_credit_compensation_proof(
        class_id=original.class_id,
        target_seat_id=original.seat_id,
        origin_locator=ledger_origin_locator(original),
        through_posting_sequence=get_account_posting_boundary(
            original.seat_id, original.class_id, original.account_type
        )
        or 0,
        creation_evidence=inputs["creation_evidence"],
    )


def test_pending_generic_exact_reversal_preserves_existing_authority(app):
    classroom, original = _original(app, posted=False)
    with FEATContext("FEAT-LED-002", idempotency_key="cap:exact"):
        inputs = positive_reversal_inputs(original)
        proof = _proof(original, inputs)
        assert proof.status == "PENDING"
        with pytest.raises(RecoveryIntegrityError):
            resolve_credit_recovery(
                proof=proof,
                recovery_kind="RESIDUAL",
                correction_intent_locator="cap:residual",
                banking_directive=inputs["banking_directive"],
                actor_seat_id=classroom.teacher_seat_id,
                mechanism="teacher",
            )
        plan = resolve_credit_recovery(
            proof=proof,
            recovery_kind="EXACT_REVERSAL",
            correction_intent_locator="cap:exact",
            banking_directive=inputs["banking_directive"],
            actor_seat_id=classroom.teacher_seat_id,
            mechanism="teacher",
        )
        result = apply_credit_recovery(plan=plan, idempotency_key="cap:exact")
        assert result["principal"].compensation_amount_cents == 1000
    db.session.commit()
    with FEATContext("FEAT-LED-002", idempotency_key="cap:after"):
        inputs = positive_reversal_inputs(original)
        proof = _proof(original, inputs)
        assert proof.recovered_cents == 1000
        assert proof.remaining_cents == 0
        with pytest.raises(RecoveryIntegrityError):
            resolve_credit_recovery(
                proof=proof,
                recovery_kind="EXACT_REVERSAL",
                correction_intent_locator="cap:second",
                banking_directive=inputs["banking_directive"],
                actor_seat_id=classroom.teacher_seat_id,
                mechanism="teacher",
            )


def test_database_cap_rejects_over_recovery_before_audit_commit(app):
    classroom, original = _original(app)
    with pytest.raises(DBAPIError, match="(?i)cap|exceed|recovery"):
        with FEATContext("FEAT-LED-002", idempotency_key="cap:too-much"):
            create_pending_transaction(
                seat_id=original.seat_id,
                class_id=original.class_id,
                actor_seat_id=classroom.teacher_seat_id,
                target_seat_id=original.seat_id,
                mechanism="teacher",
                amount=Decimal("-10.01"),
                account_type="checking",
                type="payroll_correction",
                description="Invalid oversized recovery",
                idempotency_key="cap:too-much",
                compensation_origin_locator=ledger_origin_locator(original),
                correction_intent_locator="cap:too-much",
                compensation_amount_cents=1001,
            )
    db.session.rollback()
    with FEATContext("FEAT-LED-002", idempotency_key="cap:inspect"):
        assert _proof(original, positive_reversal_inputs(original)).recovered_cents == 0


def test_missing_or_extra_evidence_cannot_authorize_recovery(app):
    classroom, original = _original(app)
    with FEATContext("FEAT-LED-002", idempotency_key="cap:evidence"):
        inputs = positive_reversal_inputs(original)
        assert _proof(original, inputs).status == "VERIFIED"
        assert _proof(original, {"creation_evidence": ()}).status == "UNAVAILABLE"
        unrelated = record_ledger_fixture(
            seat_id=original.seat_id,
            class_id=original.class_id,
            amount=Decimal("1.00"),
            actor_seat_id=classroom.teacher_seat_id,
            mechanism="teacher",
        )
        extra = positive_reversal_inputs(unrelated)["creation_evidence"]
        assert (
            _proof(
                original, {"creation_evidence": inputs["creation_evidence"] + extra}
            ).status
            == "UNAVAILABLE"
        )


def _raw_recovery_values(classroom, original):
    return dict(
        class_id=original.class_id, seat_id=original.seat_id,
        actor_seat_id=classroom.teacher_seat_id, target_seat_id=original.seat_id,
        amount=Decimal("-0.01"), amount_cents=-1, account_type="checking",
        type="payroll_correction", mechanism="teacher", description="Guard probe",
        correlation_id="corr_guard_probe", posting_sequence=original.posting_sequence + 1,
        compensation_origin_locator=ledger_origin_locator(original),
        correction_intent_locator="raw:invalid", compensation_amount_cents=1,
        feat_code="FEAT-PROD-005",
    )


def _raw_insert_recovery(values):
    from sqlalchemy import text

    columns = ",".join(values)
    parameters = ",".join(":" + key for key in values)
    return db.session.execute(
        text(f"INSERT INTO ledger_transaction ({columns},timestamp) VALUES ({parameters},now()) RETURNING id"),
        values,
    ).scalar_one()


@pytest.mark.parametrize(
    "changed,expected",
    [
        ({"compensation_amount_cents": None}, "explicit attributable recovery"),
        ({"compensation_amount_cents": -1}, "explicit attributable recovery"),
        ({"compensation_amount_cents": 1001}, "Invalid attributable Ledger recovery"),
        ({"compensation_origin_locator": "ledger-credit:v1:999999999"}, "Invalid attributable Ledger recovery"),
        ({"amount_cents": -2}, "Invalid attributable Ledger recovery"),
        ({"compensation_amount_cents": 1001, "amount_cents": -1001, "amount": Decimal("-10.01")}, "Ledger recovery cap exceeded"),
    ],
)
def test_raw_postgres_rejects_invalid_compensation_metadata(app, changed, expected):
    classroom, original = _original(app)
    values = dict(_raw_recovery_values(classroom, original), **changed)
    # Prove the immediate monetary guard, without allowing a deferred missing-
    # lineage error at commit to hide a missing metadata/cap constraint.
    with pytest.raises(DBAPIError, match=expected):
        _raw_insert_recovery(values)
    db.session.rollback()


def test_valid_raw_recovery_passes_immediate_guards_and_is_rolled_back(app):
    from app.models import Transaction

    classroom, original = _original(app)
    before = Transaction.query.count()
    row_id = _raw_insert_recovery(_raw_recovery_values(classroom, original))
    assert Transaction.query.count() == before + 1
    assert db.session.get(Transaction, row_id).compensation_amount_cents == 1
    # This is only a structural INSERT control. It has no lawful creation
    # lineage and must never commit or be used as compensation evidence.
    db.session.rollback()
    assert Transaction.query.count() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("compensation_amount_cents", 1),
        ("compensation_origin_locator", "ledger-credit:v1:1"),
        ("correction_intent_locator", "immutable:replacement"),
    ],
)
def test_raw_postgres_cannot_rewrite_compensation_fields(app, field, value):
    from sqlalchemy import text

    _, original = _original(app)
    with pytest.raises(DBAPIError, match="(?i)immutable"):
        db.session.execute(
            text(f"UPDATE ledger_transaction SET {field} = :value WHERE id = :id"),
            {"value": value, "id": original.id},
        )
    db.session.rollback()


def test_raw_postgres_recovery_intent_is_unique_per_original(app):
    from sqlalchemy import text
    from app.models import Transaction
    from tests.dom.prod.test_attendance_invalidation_command import (
        _paid_sources,
        _args,
        _accept,
        preview,
    )

    _, ctx, target, pairs, _ = _paid_sources(app)
    args = _args(ctx, target, pairs[0])
    _accept(args, identity=preview(**args).identity)
    principal = Transaction.query.filter(
        Transaction.class_id == ctx.class_id, Transaction.compensation_amount_cents > 0
    ).one()
    columns = [
        column.name for column in Transaction.__table__.columns if column.name != "id"
    ]
    selection = [
        (
            "(SELECT max(posting_sequence)+1 FROM ledger_transaction WHERE class_id=:class_id)"
            if name == "posting_sequence"
            else name
        )
        for name in columns
    ]
    statement = f"INSERT INTO ledger_transaction ({','.join(columns)}) SELECT {','.join(selection)} FROM ledger_transaction WHERE id=:id"
    with pytest.raises(IntegrityError, match="uq_ledger_recovery_intent"):
        db.session.execute(
            text(statement), {"id": principal.id, "class_id": ctx.class_id}
        )
    db.session.rollback()


def test_exact_savings_credit_reversal_keeps_original_account(app):
    classroom, original = _original(app, account_type="savings")
    original_values = {column.key: getattr(original, column.key) for column in original.__table__.columns}
    with FEATContext("FEAT-LED-002", idempotency_key="cap:savings-exact"):
        inputs = positive_reversal_inputs(original)
        plan = resolve_credit_recovery(
            proof=_proof(original, inputs),
            recovery_kind="EXACT_REVERSAL",
            correction_intent_locator="cap:savings-exact",
            banking_directive=inputs["banking_directive"],
            actor_seat_id=classroom.teacher_seat_id,
            mechanism="teacher",
        )
        assert plan.resolved_plan.recovery_transfer_amount == Decimal("0.00")
        result = apply_credit_recovery(plan=plan, idempotency_key="cap:savings-exact")
        assert len(result["effects"]) == 1
        assert result["principal"].account_type == "savings"
        assert result["principal"].amount_cents == -1000
        assert result["principal"].original_transaction_id == original.id
        assert result["principal"].correlation_id == original.correlation_id
        assert {column.key: getattr(original, column.key) for column in original.__table__.columns} == original_values


def test_credit_recovery_overdraft_has_no_fee_or_fee_configuration_dependency(
    app, monkeypatch
):
    from dataclasses import replace
    import app.services.class_configuration_query_service as configuration

    classroom, original = _original(app)
    with FEATContext("FEAT-LED-001", idempotency_key="cap:spend"):
        record_ledger_fixture(
            seat_id=original.seat_id,
            class_id=original.class_id,
            amount=Decimal("-10.00"),
            type="purchase",
        )
    db.session.commit()

    def unavailable_cwi(*args, **kwargs):
        raise AssertionError("A credit recovery must not evaluate fee CWI")

    monkeypatch.setattr(configuration, "calculate_cwi", unavailable_cwi)
    with FEATContext("FEAT-LED-002", idempotency_key="cap:no-fee"):
        inputs = positive_reversal_inputs(original)
        directive = replace(
            inputs["banking_directive"],
            protection_enabled=False,
            flat_fee=Decimal("99.00"),
        )
        plan = resolve_credit_recovery(
            proof=_proof(original, inputs),
            recovery_kind="EXACT_REVERSAL",
            correction_intent_locator="cap:no-fee",
            banking_directive=directive,
            actor_seat_id=classroom.teacher_seat_id,
            mechanism="teacher",
        )
        assert plan.resolved_plan.checking_after == Decimal("-10.00")
        assert plan.resolved_plan.overdraft_fee_amount == Decimal("0.00")
        result = apply_credit_recovery(plan=plan, idempotency_key="cap:no-fee")
        assert len(result["effects"]) == 1
        assert result["principal"].compensation_amount_cents == 1000


def test_raw_postgres_rejects_cross_class_credit_origin(app):
    from app.models import Transaction
    _, original = _original(app)
    other = provision_ledger_classroom('biology_block_a', app)
    with pytest.raises(DBAPIError, match='Invalid attributable Ledger recovery'):
        db.session.execute(Transaction.__table__.insert().values(
            class_id=other.class_id, seat_id=other.students[0].seat.id,
            actor_seat_id=other.teacher_seat_id, target_seat_id=other.students[0].seat.id,
            mechanism='teacher', amount=Decimal('-0.01'), amount_cents=-1,
            account_type='checking', type='payroll_correction', description='Cross-class probe',
            correlation_id='corr_cross_class_guard', feat_code='FEAT-PROD-005', posting_sequence=1,
            compensation_origin_locator=ledger_origin_locator(original),
            correction_intent_locator='raw:cross-class', compensation_amount_cents=1,
        ))
    db.session.rollback()
