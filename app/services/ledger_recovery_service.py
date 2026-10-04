"""Ledger-owned signed compensation proof and bounded atomic credit recovery."""

from dataclasses import dataclass
from decimal import Decimal
import re
from app.extensions import db
from app.models import Transaction, Seat, ClassEconomy, LedgerCommandReservation
from app.services.ledger_balance_query_service import get_account_posting_boundary
from app.services.ledger_evidence import (
    LedgerCreationEvidence,
    evidence_matches as _evidence_matches,
)
from app.services.ledger_resolution_service import (
    build_intended_ledger_plan,
    resolve_intended_ledger_plan,
    apply_resolved_ledger_plan,
)


class RecoveryIntegrityError(ValueError):
    pass


@dataclass(frozen=True)
class CreditCompensationProof:
    status: str
    origin_locator: str
    original: object | None = None
    original_cents: int = 0
    recovered_cents: int = 0
    remaining_cents: int = 0
    material: tuple = ()
    creation_evidence: tuple = ()


@dataclass(frozen=True)
class CreditRecoveryPlan:
    proof: CreditCompensationProof
    recovery_kind: str
    correction_intent_locator: str
    allocated_cents: int
    resolved_plan: object
    material: tuple


def ledger_origin_locator(transaction):
    return f"ledger-credit:v1:{transaction.id}"


def ledger_effect_locator(transaction):
    return f"ledger-effect:v1:{transaction.id}"


def _origin(class_id, target_seat_id, locator, lock=False):
    match = re.fullmatch("ledger-credit:v1:([1-9][0-9]*)", str(locator))
    if match is None:
        return None
    query = Transaction.query.filter_by(
        id=int(match.group(1)),
        class_id=class_id,
        seat_id=target_seat_id,
        target_seat_id=target_seat_id,
    )
    return query.with_for_update().first() if lock else query.first()


def lock_recovery_scope(class_id, target_seat_id, origin_locator=None):
    if (
        Seat.query.filter_by(id=target_seat_id, class_id=class_id)
        .with_for_update()
        .first()
        is None
    ):
        raise RecoveryIntegrityError("Invalid scoped seat.")
    ClassEconomy.query.filter_by(class_id=class_id).with_for_update().one()
    if (
        origin_locator is not None
        and _origin(class_id, target_seat_id, origin_locator, True) is None
    ):
        raise RecoveryIntegrityError("Unavailable scoped original credit.")


def get_credit_compensation_proof(
    *,
    class_id,
    target_seat_id,
    origin_locator,
    through_posting_sequence,
    creation_evidence,
):
    unknown = CreditCompensationProof("UNAVAILABLE", origin_locator)
    expected = get_credit_recovery_evidence_records(
        class_id=class_id, target_seat_id=target_seat_id, origin_locator=origin_locator
    )
    if any(not isinstance(item, LedgerCreationEvidence) for item in creation_evidence):
        return unknown
    if any(
        item.class_id != class_id or item.table_name != "ledger_transaction"
        for item in creation_evidence
    ):
        return unknown
    if len(creation_evidence) != len(expected) or {str(row.id) for row in expected} != {
        item.row_pk for item in creation_evidence
    }:
        return unknown
    original = _origin(class_id, target_seat_id, origin_locator)
    if (
        original is None
        or original.amount_cents <= 0
        or original.amount_cents != int(Decimal(original.amount) * 100)
    ):
        return unknown
    fields = (
        "class_id",
        "target_seat_id",
        "actor_seat_id",
        "amount_cents",
        "account_type",
        "type",
        "correlation_id",
        "posting_sequence",
    )
    if not _evidence_matches(original, class_id, creation_evidence, fields):
        return unknown
    if (
        type(through_posting_sequence) is not int
        or through_posting_sequence < 0
        or original.posting_sequence is None
    ):
        return unknown
    status = (
        "PENDING"
        if original.posting_sequence > through_posting_sequence
        else "VERIFIED"
    )
    old = Transaction.query.filter(
        Transaction.class_id == class_id,
        Transaction.seat_id == target_seat_id,
        Transaction.amount_cents < 0,
        Transaction.posting_sequence > original.posting_sequence,
        db.or_(
            Transaction.lineage_version.is_(None),
            Transaction.lineage_version.in_([1, 2]),
        ),
    ).all()
    if any(
        (
            row.type in {"REVERSAL", "payroll", "payroll_correction"}
            or row.correlation_id == original.correlation_id
            or row.id == original.reversal_transaction_id
            or (row.original_transaction_id == original.id)
            for row in old
        )
    ):
        return unknown
    recoveries = (
        Transaction.query.filter_by(
            class_id=class_id,
            target_seat_id=target_seat_id,
            compensation_origin_locator=origin_locator,
        )
        .order_by(Transaction.posting_sequence)
        .all()
    )
    recovered = 0
    identities = []
    intents = set()
    for row in recoveries:
        if (
            row.lineage_version != 3
            or row.seat_id != target_seat_id
            or row.account_type != original.account_type
            or (type(row.compensation_amount_cents) is not int)
            or (row.compensation_amount_cents <= 0)
            or (row.amount_cents != -row.compensation_amount_cents)
            or (not row.correction_intent_locator)
            or (row.correction_intent_locator in intents)
            or (
                not _evidence_matches(
                    row,
                    class_id,
                    creation_evidence,
                    fields
                    + (
                        "compensation_origin_locator",
                        "compensation_amount_cents",
                        "correction_intent_locator",
                    ),
                )
            )
        ):
            return unknown
        recovered += row.compensation_amount_cents
        intents.add(row.correction_intent_locator)
        identities.append(
            (
                row.id,
                row.posting_sequence,
                row.compensation_amount_cents,
                row.correction_intent_locator,
                row.lineage_event_id,
            )
        )
    if recovered > original.amount_cents:
        return unknown
    material = (
        origin_locator,
        original.id,
        original.amount_cents,
        original.posting_sequence,
        original.lineage_event_id,
        original.lineage_version,
        tuple(identities),
    )
    return CreditCompensationProof(
        status,
        origin_locator,
        original,
        original.amount_cents,
        recovered,
        original.amount_cents - recovered,
        material,
        tuple(creation_evidence),
    )


def resolve_credit_recovery(
    *,
    proof,
    recovery_kind,
    correction_intent_locator,
    banking_directive,
    actor_seat_id,
    mechanism,
    allocation_proof=None,
    interval_key=None,
    description="Payroll correction",
):
    if proof.status != "VERIFIED" and (
        not (proof.status == "PENDING" and recovery_kind == "EXACT_REVERSAL")
    ):
        raise RecoveryIntegrityError("PROVENANCE_UNAVAILABLE")
    if recovery_kind == "INTERVAL":
        if (
            not allocation_proof
            or allocation_proof.get("status") != "verified"
            or allocation_proof.get("transaction").id != proof.original.id
        ):
            raise RecoveryIntegrityError("PROVENANCE_UNAVAILABLE")
        allocated = allocation_proof["allocations"].get(tuple(interval_key))
        if type(allocated) is not int or allocated < 0:
            raise RecoveryIntegrityError("INTEGRITY_FAILURE")
        if proof.remaining_cents == 0:
            allocated = 0
        elif allocated > proof.remaining_cents:
            raise RecoveryIntegrityError("INTEGRITY_FAILURE")
    elif recovery_kind == "RESIDUAL":
        allocated = proof.remaining_cents
    elif recovery_kind == "EXACT_REVERSAL":
        if proof.recovered_cents:
            raise RecoveryIntegrityError("PRIOR_COMPENSATION")
        allocated = proof.original_cents
    else:
        raise RecoveryIntegrityError("Invalid recovery kind.")
    if not correction_intent_locator or len(correction_intent_locator) > 128:
        raise RecoveryIntegrityError("Invalid correction intent.")
    p = proof.original
    intended = build_intended_ledger_plan(
        seat_id=p.seat_id,
        class_id=p.class_id,
        debit_amount=Decimal(allocated) / 100,
        description=description,
        transaction_type=(
            "REVERSAL" if recovery_kind == "EXACT_REVERSAL" else "payroll_correction"
        ),
        actor_seat_id=actor_seat_id,
        target_seat_id=p.target_seat_id,
        mechanism=mechanism,
        source_account=p.account_type,
        compensation_origin_locator=proof.origin_locator if allocated else None,
        correction_intent_locator=correction_intent_locator if allocated else None,
        original_transaction_id=p.id if recovery_kind == "EXACT_REVERSAL" else None,
        correlation_id=p.correlation_id if recovery_kind == "EXACT_REVERSAL" else None,
    )
    resolved = resolve_intended_ledger_plan(
        plan=intended, banking_directive=banking_directive, fee_authority="NONE"
    )
    material = (
        proof.material,
        recovery_kind,
        correction_intent_locator,
        allocated,
        resolved.directive_identity,
        str(resolved.checking_before),
        str(resolved.savings_before),
        str(resolved.recovery_transfer_amount),
    )
    return CreditRecoveryPlan(
        proof, recovery_kind, correction_intent_locator, allocated, resolved, material
    )


def apply_credit_recovery(*, plan, idempotency_key):
    """No new FEAT; reprove recovery cap under the canonical shared serialization."""
    original = plan.proof.original
    lock_recovery_scope(original.class_id, original.seat_id, plan.proof.origin_locator)
    fresh = get_credit_compensation_proof(
        class_id=original.class_id,
        target_seat_id=original.seat_id,
        origin_locator=plan.proof.origin_locator,
        through_posting_sequence=(
            get_account_posting_boundary(
                original.seat_id, original.class_id, original.account_type
            )
            or 0
            if plan.recovery_kind == "EXACT_REVERSAL"
            else get_account_posting_boundary(
                original.seat_id, original.class_id, original.account_type
            )
        ),
        creation_evidence=plan.proof.creation_evidence,
    )
    if (
        fresh.status != "VERIFIED"
        and (not (fresh.status == "PENDING" and plan.recovery_kind == "EXACT_REVERSAL"))
        or fresh.material != plan.proof.material
    ):
        raise RecoveryIntegrityError("PREVIEW_CHANGED")
    if plan.allocated_cents > fresh.remaining_cents:
        raise RecoveryIntegrityError("INTEGRITY_FAILURE")
    from app.services.ledger_balance_query_service import get_available_balances

    checking, savings = get_available_balances(original.seat_id, original.class_id)
    if (
        checking != plan.resolved_plan.checking_before
        or savings != plan.resolved_plan.savings_before
    ):
        raise RecoveryIntegrityError("PREVIEW_CHANGED")
    result = apply_resolved_ledger_plan(
        resolved_plan=plan.resolved_plan, idempotency_key=idempotency_key
    )
    principal = result["principal"]
    if principal and plan.recovery_kind == "EXACT_REVERSAL":
        original.reversal_transaction_id = principal.id
        db.session.flush()
    return dict(
        result,
        origin_locator=plan.proof.origin_locator,
        principal_locator=ledger_effect_locator(principal) if principal else None,
        effect_locators=tuple(
            (ledger_effect_locator(row) for row in result["effects"])
        ),
    )


def get_recovery_outcome(
    *, class_id, target_seat_id, effect_locators, creation_evidence
):
    """Resolve immutable accepted result locators without repricing/recovery evaluation."""
    rows = []
    for locator in effect_locators:
        match = re.fullmatch("ledger-effect:v1:([1-9][0-9]*)", str(locator))
        if match is None:
            raise RecoveryIntegrityError("PROVENANCE_UNAVAILABLE")
        row = Transaction.query.filter_by(
            id=int(match.group(1)), class_id=class_id, seat_id=target_seat_id
        ).first()
        if row is None or not _evidence_matches(
            row,
            class_id,
            creation_evidence,
            (
                "amount_cents",
                "compensation_origin_locator",
                "compensation_amount_cents",
                "correction_intent_locator",
            ),
        ):
            raise RecoveryIntegrityError("PROVENANCE_UNAVAILABLE")
        rows.append(row)
    if len({row.command_reservation_id for row in rows}) > 1:
        raise RecoveryIntegrityError("INTEGRITY_FAILURE")
    return {
        "effect_locators": tuple(effect_locators),
        "recovered_cents": sum((row.compensation_amount_cents for row in rows)),
        "principal_locator": next(
            (
                ledger_effect_locator(row)
                for row in rows
                if row.compensation_amount_cents > 0
            ),
            None,
        ),
    }


def resolve_payroll_credit_locator(
    *,
    class_id,
    target_seat_id,
    correlation_id,
    idempotency_key,
    originating_actor_seat_id,
    originating_mechanism,
    original_event_type,
):
    rows = Transaction.query.filter_by(
        class_id=class_id,
        seat_id=target_seat_id,
        target_seat_id=target_seat_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    ).all()
    expected = {"payroll": "payroll", "manual_credit": "manual_payment"}.get(
        original_event_type
    )
    if len(rows) != 1 or expected is None:
        return None
    row = rows[0]
    mechanism = getattr(row.mechanism, "value", row.mechanism)
    if (
        row.actor_seat_id != originating_actor_seat_id
        or str(mechanism).lower() != str(originating_mechanism).lower()
        or row.type != expected
        or (row.amount_cents <= 0)
    ):
        return None
    return ledger_origin_locator(row)


def get_credit_recovery_evidence_records(*, class_id, target_seat_id, origin_locator):
    original = _origin(class_id, target_seat_id, origin_locator)
    if original is None:
        return ()
    rows = (
        Transaction.query.filter(
            Transaction.class_id == class_id,
            Transaction.seat_id == target_seat_id,
            db.or_(
                Transaction.compensation_origin_locator == origin_locator,
                db.and_(
                    Transaction.amount_cents < 0,
                    Transaction.posting_sequence > original.posting_sequence,
                    db.or_(
                        Transaction.lineage_version.is_(None),
                        Transaction.lineage_version < 3,
                    ),
                    db.or_(
                        Transaction.type.in_(
                            ["REVERSAL", "payroll", "payroll_correction"]
                        ),
                        Transaction.correlation_id == original.correlation_id,
                        Transaction.id == original.reversal_transaction_id,
                        Transaction.original_transaction_id == original.id,
                    ),
                ),
            ),
        )
        .order_by(Transaction.posting_sequence)
        .all()
    )
    return (original,) + tuple(rows)


def get_recovery_outcome_records(*, class_id, target_seat_id, effect_locators):
    rows = []
    for locator in effect_locators:
        match = re.fullmatch("ledger-effect:v1:([1-9][0-9]*)", str(locator))
        if match is None:
            raise RecoveryIntegrityError("PROVENANCE_UNAVAILABLE")
        row = Transaction.query.filter_by(
            id=int(match.group(1)), class_id=class_id, seat_id=target_seat_id
        ).first()
        if row is None:
            raise RecoveryIntegrityError("PROVENANCE_UNAVAILABLE")
        rows.append(row)
    return tuple(rows)
