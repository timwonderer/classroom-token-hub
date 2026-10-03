"""Ledger-owned pure allocation/proof; no attendance or policy interpretation."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction
from datetime import datetime

from app.extensions import db
from app.models import Transaction, TransactionStatus
from app.utils.canonical_temporal_resolver import ensure_utc


class AllocationIntegrityError(ValueError):
    pass


def allocate_payroll_cents(pricing, *, original_credit, allocation_version):
    if type(allocation_version) is not int or allocation_version != 1:
        raise AllocationIntegrityError("Original allocation version is unavailable.")
    total = Decimal(str(original_credit))
    if not total.is_finite() or total < 0 or total != total.quantize(Decimal(".01")):
        raise AllocationIntegrityError("Invalid original credit.")
    allocations, expected = {}, 0
    for share in pricing:
        seconds = share["seconds"]
        rate = Decimal(share["pay_rate_per_minute"])
        sources = share["intervals"]
        if type(seconds) is not int or seconds < 0 or not rate.is_finite() or rate < 0:
            raise AllocationIntegrityError("Invalid original pricing inputs.")
        cents = int((Decimal(seconds) * rate / Decimal(60)).quantize(Decimal(".01"), rounding=ROUND_HALF_EVEN) * 100)
        if any(type(i["credited_seconds"]) is not int or i["credited_seconds"] < 0 for i in sources):
            raise AllocationIntegrityError("Invalid credited seconds.")
        if sum(i["credited_seconds"] for i in sources) != seconds:
            raise AllocationIntegrityError("Membership does not sum to its pricing share.")
        ranked, allocated = [], 0
        for source in sources:
            key = (source["opening_event_id"], source["closing_event_id"])
            if any(type(value) is not int or value <= 0 for value in key):
                raise AllocationIntegrityError("Invalid interval source identifiers.")
            if key in allocations:
                raise AllocationIntegrityError("Duplicate interval membership.")
            quotient = Fraction(cents * source["credited_seconds"], seconds) if seconds else Fraction(0)
            floor = quotient.numerator // quotient.denominator
            allocations[key] = floor
            allocated += floor
            closed_at = datetime.fromisoformat(source["closing_timestamp"])
            if closed_at.tzinfo is None:
                raise AllocationIntegrityError("Closing timestamp must carry UTC offset.")
            ranked.append((-(quotient-floor), ensure_utc(closed_at), key[0], key[1], key))
        for *_, key in sorted(ranked)[:cents-allocated]:
            allocations[key] += 1
        expected += cents
    if expected != int(total * 100):
        raise AllocationIntegrityError("Original credit does not equal frozen pricing shares.")
    return allocations


def payroll_allocation_proof(*, class_id, target_seat_id, correlation_id, idempotency_key, allocation_version, pricing, originating_actor_seat_id, originating_mechanism, through_posting_sequence=None):
    """Receive PROD-proven membership; resolve one exact monetary effect, fail closed."""
    unavailable = {"status": "provenance_unavailable", "allocations": {}, "transaction": None}
    rows = Transaction.query.filter_by(class_id=class_id, target_seat_id=target_seat_id,
        correlation_id=correlation_id, idempotency_key=idempotency_key).all()
    if len(rows) != 1:
        return unavailable
    credit = rows[0]
    mechanism = getattr(credit.mechanism, "value", credit.mechanism)
    if (credit.seat_id != target_seat_id or credit.actor_seat_id != originating_actor_seat_id
            or str(mechanism).lower() != str(originating_mechanism).lower()
            or Decimal(credit.amount) < 0 or credit.account_type != "checking"):
        return unavailable
    from app.utils.audit_verifier import verify_record_creation_lineage
    if credit.type != "payroll" or credit.original_transaction_id is not None or credit.feat_code not in {"FEAT-PROD-003", "FEAT-PROD-004"}:
        return unavailable
    if not verify_record_creation_lineage("ledger_transaction", credit, class_id,
            required_fields=("class_id", "actor_seat_id", "target_seat_id", "mechanism", "amount_cents",
                "account_type", "correlation_id", "feat_code", "idempotency_key", "type",
                "command_reservation_id", "posting_sequence")):
        return unavailable
    reservation = credit.command_reservation
    if (credit.amount_cents != int(Decimal(credit.amount) * 100) or reservation is None
            or reservation.class_id != class_id or reservation.feat_code != credit.feat_code
            or reservation.idempotency_key != idempotency_key):
        return unavailable
    if through_posting_sequence is None or type(through_posting_sequence) is not int or through_posting_sequence < 0:
        return unavailable
    if credit.posting_sequence is None:
        return unavailable
    if credit.posting_sequence > through_posting_sequence:
        return {"status": "pending", "allocations": {}, "transaction": credit}
    try:
        allocations = allocate_payroll_cents(pricing, original_credit=credit.amount,
            allocation_version=allocation_version)
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return unavailable
    return {"status": "verified", "allocations": allocations, "transaction": credit}
