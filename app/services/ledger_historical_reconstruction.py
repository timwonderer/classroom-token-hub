"""Ledger-owned internally validated historical settlement and recovery.

DOM-LED-001 VII.1A/IX: this evidence records a reconstruction, never upgrades
an original audit signature or substitutes for modern creation evidence.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction

from app.extensions import db
from app.models import Transaction
from app.services.ledger_balance_query_service import get_account_posting_boundary
from app.services.ledger_evidence import evidence_matches
from app.services.ledger_recovery_service import (
    CreditCompensationProof,
    RecoveryIntegrityError,
    ledger_origin_locator,
)


@dataclass(frozen=True)
class ReconstructedOrigin:
    event_id: int
    proof: object
    allocations: tuple
    recovered_intervals: tuple


@dataclass(frozen=True)
class ReconstructedSettlement:
    graph: object
    origins: tuple
    material: tuple
    creation_evidence: tuple = ()


def reconstructed_interval_contribution(settlement, interval_key):
    """Fixed original contribution for display, independent of later recovery."""
    members = [
        o for o in settlement.origins if tuple(interval_key) in dict(o.allocations)
    ]
    return {
        "allocated_cents": sum(
            dict(o.allocations)[tuple(interval_key)] for o in members
        ),
        "status": (
            "pending"
            if any(o.proof.status == "PENDING" for o in members)
            else "verified" if members else "zero_cent"
        ),
        "event_ids": tuple(o.event_id for o in members),
    }


def _deny(code="PROVENANCE_UNAVAILABLE"):
    raise RecoveryIntegrityError(code)


def _money(row):
    amount = Decimal(row.amount)
    if (
        str(row.type).upper() == "VOID"
        or not amount.is_finite()
        or amount != amount.quantize(Decimal(".01"))
        or type(row.amount_cents) is not int
        or int(amount * 100) != row.amount_cents
        or type(row.posting_sequence) is not int
        or row.posting_sequence <= 0
    ):
        _deny("INTEGRITY_FAILURE")
    return row.amount_cents


def bind_historical_credit(event, records):
    expected = {"payroll": "payroll", "manual_credit": "manual_payment"}.get(
        event.event_type
    )
    candidates = [
        r
        for r in records
        if r.amount_cents > 0
        and (
            (event.correlation_id and r.correlation_id == event.correlation_id)
            or (event.command_key and r.idempotency_key == event.command_key)
        )
    ]
    if len(candidates) != 1:
        _deny()
    row = candidates[0]
    if (
        row.class_id != event.class_id
        or row.target_seat_id != event.target_seat_id
        or row.seat_id != event.target_seat_id
        or row.actor_seat_id != event.actor_seat_id
        or str(getattr(row.mechanism, "value", row.mechanism)).lower()
        != str(event.mechanism).lower()
        or row.account_type != "checking"
        or row.type != expected
        or row.original_transaction_id is not None
    ):
        _deny()
    _money(row)
    return row


def _share_cents(share, arithmetic_rule):
    rate = Decimal(share.rate_per_minute)
    if (
        not rate.is_finite()
        or rate < 0
        or type(share.credited_seconds) is not int
        or share.credited_seconds < 0
    ):
        _deny("INTEGRITY_FAILURE")
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN

        def price(seconds):
            value = (
                Decimal(seconds) * (rate / 60)
                if arithmetic_rule == "divide_first_half_even_28"
                else Decimal(seconds) * rate / 60
            )
            return int(value.quantize(Decimal(".01")) * 100)

        cents = price(share.credited_seconds)
        if share.paid_seconds is not None:
            if (
                type(share.paid_seconds) is not int
                or not 0 <= share.paid_seconds < share.credited_seconds
            ):
                _deny("INTEGRITY_FAILURE")
            cents -= price(share.paid_seconds)
        return cents


def allocate_reconstructed_shares(shares, arithmetic_rule):
    """Original aggregate quantization, then grouped rational largest remainder."""
    if arithmetic_rule not in {
        "divide_first_half_even_28",
        "multiply_first_half_even_28",
    }:
        _deny()
    allocations, total = {}, 0
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        for share in shares:
            rate = Decimal(share.rate_per_minute)
            if (
                not rate.is_finite()
                or rate < 0
                or type(share.credited_seconds) is not int
                or share.credited_seconds < 0
            ):
                _deny("INTEGRITY_FAILURE")

            def price(seconds):
                value = (
                    Decimal(seconds) * (rate / 60)
                    if arithmetic_rule == "divide_first_half_even_28"
                    else Decimal(seconds) * rate / 60
                )
                return int(value.quantize(Decimal(".01")) * 100)

            cents = price(share.credited_seconds)
            if share.paid_seconds is not None:
                if (
                    type(share.paid_seconds) is not int
                    or not 0 <= share.paid_seconds < share.credited_seconds
                ):
                    _deny("INTEGRITY_FAILURE")
                cents -= price(share.paid_seconds)
                if cents <= 0:
                    _deny("INTEGRITY_FAILURE")
            weights = {}
            closes = {}
            for weight in share.weights:
                key = (weight.opening_event_id, weight.closing_event_id)
                if (
                    key in weights
                    or any(type(v) is not int or v <= 0 for v in key)
                    or type(weight.duration_microseconds) is not int
                    or weight.duration_microseconds < 0
                ):
                    _deny("INTEGRITY_FAILURE")
                weights[key] = weight.duration_microseconds
                closes[key] = weight.closing_timestamp
            denominator = sum(weights.values())
            if cents and not denominator:
                _deny("INTEGRITY_FAILURE")
            ranked, floors = [], {}
            for key, duration in weights.items():
                value = (
                    Fraction(cents * duration, denominator)
                    if denominator
                    else Fraction(0)
                )
                floors[key] = value.numerator // value.denominator
                ranked.append((-(value - floors[key]), closes[key], *key, key))
            for *_, key in sorted(ranked)[: cents - sum(floors.values())]:
                floors[key] += 1
            if sum(floors.values()) != cents:
                _deny("INTEGRITY_FAILURE")
            for key, value in floors.items():
                allocations[key] = allocations.get(key, 0) + value
            total += cents
    return total, tuple(sorted(allocations.items()))


def validate_historical_settlement(
    *, ctx, graph, audit_observations, creation_evidence, business_creation_evidence=()
):
    """Re-read all monetary sources; validate arithmetic and complete recovery."""
    if ctx.class_id != graph.class_id or ctx.actor_role != "teacher" or not ctx.seat_id:
        _deny("UNAUTHORIZED_SCOPE")
    with db.session.no_autoflush:
        records = (
            Transaction.query.filter_by(
                class_id=graph.class_id,
                seat_id=graph.target_seat_id,
                target_seat_id=graph.target_seat_id,
            )
            .order_by(Transaction.id)
            .limit(1001)
            .all()
        )
    if len(records) > 1000:
        _deny("EVIDENCE_LIMIT_EXCEEDED")
    observations = {o.row_pk: o for o in audit_observations}
    for row in records:
        observation = observations.get(str(row.id))
        if observation is None:
            _deny()
        if (
            observation.class_id != graph.class_id
            or observation.table_name != "ledger_transaction"
            or observation.envelope_status == "INVALID"
            or observation.chain_status == "INVALID"
            or "PROTECTED_PAYLOAD_MISMATCH" in observation.reasons
        ):
            _deny("INTEGRITY_FAILURE")
        if (
            row.lineage_event_id is not None
            and observation.envelope_status != "AUTHENTICATED"
        ):
            _deny()
        if row.lineage_version not in (1, 2, 3):
            _deny()
        if row.lineage_version in (2, 3) and not evidence_matches(
            row, graph.class_id, creation_evidence
        ):
            _deny()
        _money(row)
    originals, allocations, event_map = {}, {}, {e.event_id: e for e in graph.events}
    for event in graph.events:
        if event.event_type == "manual_credit":
            candidates = tuple(
                s
                for s in event.candidate_shares
                if _share_cents(s, event.arithmetic_rule) > 0
            )
            if (
                set(s.window_event_id for s in candidates)
                != set(event.referenced_event_ids)
                or {s.window_event_id: s for s in candidates}
                != {s.window_event_id: s for s in event.shares}
                or len(candidates) != len(event.referenced_event_ids)
            ):
                _deny("INTEGRITY_FAILURE")
        total, shares = allocate_reconstructed_shares(
            event.shares, event.arithmetic_rule
        )
        if total == 0:
            matches = [
                r
                for r in records
                if r.amount_cents > 0
                and (
                    (event.correlation_id and r.correlation_id == event.correlation_id)
                    or (event.command_key and r.idempotency_key == event.command_key)
                )
            ]
            if matches:
                _deny("INTEGRITY_FAILURE")
            continue
        credit = bind_historical_credit(event, records)
        if credit.lineage_version in (2, 3) and not any(
            p.table_name == "payroll_event"
            and p.row_pk == str(event.event_id)
            and p.class_id == graph.class_id
            for p in business_creation_evidence
        ):
            _deny()
        if credit.id in originals or total != credit.amount_cents:
            _deny("INTEGRITY_FAILURE")
        originals[credit.id] = (event, credit)
        allocations[credit.id] = shares
    legacy_recoveries = {}
    assigned = set()
    for reversal in graph.reversals:
        original_event_id = reversal.original_event_id
        matches = [
            (event, credit)
            for event, credit in originals.values()
            if event.event_id == original_event_id
        ]
        if not matches:
            continue
        event, credit = matches[0]
        meta = reversal.event
        candidates = [
            r
            for r in records
            if r.amount_cents < 0
            and (
                (meta.correlation_id and r.correlation_id == meta.correlation_id)
                or (meta.command_key and r.idempotency_key == meta.command_key)
            )
        ]
        if len(candidates) != 1:
            _deny()
        debit = candidates[0]
        if (
            debit.id in assigned
            or debit.amount_cents != -credit.amount_cents
            or debit.account_type != credit.account_type
            or debit.type not in {"payroll", "REVERSAL"}
            or debit.actor_seat_id != meta.actor_seat_id
            or str(getattr(debit.mechanism, "value", debit.mechanism)).lower()
            != str(meta.mechanism).lower()
        ):
            _deny("INTEGRITY_FAILURE")
        assigned.add(debit.id)
        legacy_recoveries.setdefault(credit.id, []).append(debit)
    relevant_negative = [
        r
        for r in records
        if r.amount_cents < 0
        and r.type in {"payroll", "REVERSAL", "payroll_correction"}
    ]
    origin_locators = {
        ledger_origin_locator(credit) for _, credit in originals.values()
    }
    if any(
        (r.lineage_version != 3 and r.id not in assigned)
        or (
            r.lineage_version == 3
            and (
                r.compensation_origin_locator not in origin_locators
                or not r.correction_intent_locator
                or not r.compensation_amount_cents
            )
        )
        for r in relevant_negative
    ):
        _deny("PRIOR_RECOVERY_UNAVAILABLE")
    results = []
    for event, credit in originals.values():
        origin = ledger_origin_locator(credit)
        recoveries = legacy_recoveries.get(credit.id, [])
        modern = sorted(
            (r for r in records if r.compensation_origin_locator == origin),
            key=lambda r: r.posting_sequence,
        )
        running = sum(-r.amount_cents for r in recoveries)
        intents = set()
        interval_recovered = {}
        for row in modern:
            if (
                row.lineage_version != 3
                or row.account_type != credit.account_type
                or type(row.compensation_amount_cents) is not int
                or row.compensation_amount_cents <= 0
                or row.amount_cents != -row.compensation_amount_cents
                or not row.correction_intent_locator
                or row.correction_intent_locator in intents
                or not evidence_matches(row, graph.class_id, creation_evidence)
            ):
                _deny("INTEGRITY_FAILURE")
            intents.add(row.correction_intent_locator)
            associations = [
                r
                for r in graph.recoveries
                if r.original_event_id == event.event_id
                and r.correction_intent_locator == row.correction_intent_locator
                and r.ledger_result_locator == f"ledger-effect:v1:{row.id}"
            ]
            if len(associations) != 1:
                _deny("PRIOR_RECOVERY_UNAVAILABLE")
            association = associations[0]
            signed = next(
                (
                    p
                    for p in business_creation_evidence
                    if p.table_name == "payroll_event"
                    and p.class_id == graph.class_id
                    and p.row_pk == str(association.event_id)
                ),
                None,
            )
            if signed is None:
                _deny("PRIOR_RECOVERY_UNAVAILABLE")
            values = dict(signed.field_values)
            summary = dict(values.get("summary_json", ()))
            if (
                values.get("target_seat_id") != graph.target_seat_id
                or summary.get("original_payroll_event_id") != event.event_id
                or summary.get("correction_intent_locator")
                != row.correction_intent_locator
                or summary.get("ledger_result_locator")
                != association.ledger_result_locator
            ):
                _deny("INTEGRITY_FAILURE")
            if association.kind == "INTERVAL_INVALIDATION":
                key = (association.opening_event_id, association.closing_event_id)
                if (
                    summary.get("opening_event_id"),
                    summary.get("closing_event_id"),
                ) != key:
                    _deny("INTEGRITY_FAILURE")
                expected = dict(allocations[credit.id]).get(
                    key, -1
                ) - interval_recovered.get(key, 0)
                if (
                    running == credit.amount_cents
                    or row.compensation_amount_cents != expected
                ):
                    _deny("INTEGRITY_FAILURE")
                interval_recovered[key] = (
                    interval_recovered.get(key, 0) + row.compensation_amount_cents
                )
                if interval_recovered[key] > dict(allocations[credit.id]).get(key, -1):
                    _deny("INTEGRITY_FAILURE")
            elif association.kind == "EXACT_REVERSAL":
                if running or row.compensation_amount_cents != credit.amount_cents:
                    _deny("INTEGRITY_FAILURE")
            elif association.kind == "RESIDUAL_RECOVERY":
                if row.compensation_amount_cents != credit.amount_cents - running:
                    _deny("INTEGRITY_FAILURE")
            else:
                _deny("PRIOR_RECOVERY_UNAVAILABLE")
            running += row.compensation_amount_cents
        recoveries += modern
        recovered = sum(-r.amount_cents for r in recoveries)
        if recovered > credit.amount_cents:
            _deny("INTEGRITY_FAILURE")
        boundary = get_account_posting_boundary(
            credit.seat_id, credit.class_id, credit.account_type
        )
        status = (
            "PENDING"
            if boundary is None or credit.posting_sequence > boundary
            else "VERIFIED"
        )
        material = (
            origin,
            credit.id,
            credit.amount_cents,
            credit.posting_sequence,
            tuple(
                (r.id, r.posting_sequence, r.amount_cents, r.correction_intent_locator)
                for r in recoveries
            ),
            event,
            allocations[credit.id],
            tuple(graph.reversals),
        )
        proof = CreditCompensationProof(
            status,
            origin,
            credit,
            credit.amount_cents,
            recovered,
            credit.amount_cents - recovered,
            material,
            tuple(creation_evidence),
        )
        results.append(
            ReconstructedOrigin(
                event.event_id,
                proof,
                allocations[credit.id],
                tuple(interval_recovered.items()),
            )
        )
    return ReconstructedSettlement(
        graph,
        tuple(results),
        tuple(o.proof.material for o in results),
        tuple(creation_evidence),
    )
