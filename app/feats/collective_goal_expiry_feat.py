"""Collective-goal expiry with coordinated refund (FEAT-STOR-002).

DOM-STORE-001 §5 requires that a collective-goal entitlement "record ``EXPIRED``
when the goal is not reached by the deadline and coordinate a lawful refund."
Only the purchase-time half of that existed: once a deadline passed the item
stopped selling, but everyone who had already bought in kept a ``GRANTED``
entitlement they could never exercise, and kept paying for it.

This command closes one lapsed goal in one class. It is deliberately narrow:

* **Only unmet goals are swept.** A goal reached before its deadline stays
  ``GRANTED`` — the reward is real and the teacher fulfils it by hand. Expiring
  a met goal would refund students who actually won.
* **Money and entitlement move together.** Both writes happen inside the
  caller's FEAT context, so a failure cannot leave a refunded student still
  holding the entitlement, or an expired student out of pocket.
* **It fails closed per purchase.** If the covering ledger transaction cannot be
  identified, that purchase group is skipped entirely and reported, rather than
  expired unrefunded. Leaving an entitlement ``GRANTED`` is recoverable; taking
  a student's money and giving nothing back is not.

The join between the two domains is ``correlation_id``. A store purchase writes
its ``Transaction`` and its per-unit ``EntitlementEvent`` rows under one
correlation (``store_purchase_feat``), so the events of a single purchase share
a correlation with exactly the transaction that paid for them. A bundle is n
independent entitlement lifecycles under one correlation and one charge, which
is why the refund is issued per correlation group and never per unit — refunding
per unit would return the price n times.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import EntitlementEvent, StoreProduct, Transaction
from app.services import entitlement_service
from app.services.ledger_correction_service import reverse_transaction
from app.utils.canonical_temporal_resolver import utc_now

logger = logging.getLogger(__name__)

TERMINAL_EVENT_TYPES = ("CONSUMED", "EXPIRED", "REVOKED")


@dataclass
class GoalExpiryResult:
    """What the sweep did to one goal in one class."""

    product_lineage_uuid: str
    class_id: str
    entitlements_expired: int = 0
    purchases_refunded: int = 0
    # Correlation ids whose covering transaction could not be resolved. These
    # were left untouched — entitlement and money both — and need a human.
    unresolved_correlations: list[str] = field(default_factory=list)


def _load_open_goal_entitlements(class_id: str, lineage_uuid: str) -> list[EntitlementEvent]:
    """Grants for this goal that have not yet reached a terminal disposition.

    Only ``PURCHASE`` acquisitions are returned. A teacher's direct ``GRANT``
    cost the student nothing, so there is nothing to refund; sweeping it would
    manufacture a credit out of a gift.
    """
    grants = (
        EntitlementEvent.query.filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.product_id == lineage_uuid,
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.acquisition_type == "PURCHASE",
        )
        .order_by(EntitlementEvent.timestamp.asc(), EntitlementEvent.event_id.asc())
        .all()
    )
    if not grants:
        return []

    # One terminal event per lineage is enforced by a partial unique index, so a
    # second one would fail at the database anyway. Filter them here to keep the
    # sweep idempotent: a re-run finds its own earlier work already terminal and
    # does nothing.
    terminal_ids = {
        row[0]
        for row in db.session.query(EntitlementEvent.entitlement_id)
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.entitlement_id.in_([g.entitlement_id for g in grants]),
            EntitlementEvent.event_type.in_(TERMINAL_EVENT_TYPES),
        )
        .all()
    }
    return [g for g in grants if g.entitlement_id not in terminal_ids]


def _find_covering_transaction(grant: EntitlementEvent) -> Transaction | None:
    """Locate the purchase transaction that paid for this grant.

    Matched on correlation, class, seat and type together — correlation alone is
    a shared key, not a promise of scope. A transaction that already carries a
    reversal is not returned: it was refunded by some earlier operation, and a
    second reversal would both pay the student twice and breach the one-reversal
    rule (INV-LED-013, INV-OPS-005).
    """
    if not grant.correlation_id:
        return None
    return (
        Transaction.query.filter(
            Transaction.correlation_id == grant.correlation_id,
            Transaction.class_id == grant.class_id,
            Transaction.seat_id == grant.target_seat_id,
            Transaction.type == "purchase",
            Transaction.reversal_transaction_id.is_(None),
        )
        .order_by(Transaction.id.asc())
        .first()
    )


@requires_feat_context("FEAT-STOR-002")
def expire_lapsed_collective_goal(
    *,
    product: StoreProduct,
    class_id: str,
    actor_seat_id: int,
    idempotency_key: str,
    correlation_id: str | None = None,
    reason: str = "collective_goal_unmet",
) -> GoalExpiryResult:
    """Expire every open buy-in for a lapsed, unmet goal and refund each purchase.

    The caller owns the decision that the goal lapsed and went unmet — proving
    the boundary was reached is the caller's responsibility under
    FEAT-STOR-002 §VIII. This command performs the coordinated writes.

    ``idempotency_key`` and ``correlation_id`` are consumed by
    ``requires_feat_context``, which opens the FEAT envelope; this is the FEAT
    entry, so callers must not wrap it in a context of their own (exactly one
    FEAT executes per invocation — INV-ARC-000 §VIII.2).
    """
    lineage_uuid = product.product_lineage_uuid
    result = GoalExpiryResult(product_lineage_uuid=lineage_uuid, class_id=class_id)

    open_grants = _load_open_goal_entitlements(class_id, lineage_uuid)
    if not open_grants:
        return result

    # A bundle is many entitlements under one charge, so refunds are issued per
    # purchase (correlation), not per entitlement.
    by_correlation: dict[str, list[EntitlementEvent]] = {}
    for grant in open_grants:
        by_correlation.setdefault(grant.correlation_id or "", []).append(grant)

    for correlation_id, grants in by_correlation.items():
        covering_tx = _find_covering_transaction(grants[0]) if correlation_id else None
        if covering_tx is None:
            # Fail closed. Expiring without refunding would silently keep money
            # for a goal that never happened.
            result.unresolved_correlations.append(correlation_id or "<missing>")
            logger.error(
                "Collective goal %s in class %s: could not resolve the purchase "
                "transaction for correlation %r; %d entitlement(s) left untouched "
                "for manual review rather than expired unrefunded.",
                lineage_uuid, class_id, correlation_id or "<missing>", len(grants),
            )
            continue

        # Money is reversed; only grants are voided (SPEC-OPS-001 §II.1,
        # INV-OPS-001). So there is one path here regardless of whether the
        # charge has settled: append a compensating transaction and leave the
        # original standing as historical fact (§3.2). The student sees this as
        # a refund, which §8.2 permits as user-facing language for a reversal.
        reverse_transaction(
            covering_tx,
            idempotency_key=f"goal-expiry-refund:{class_id}:{correlation_id}",
            description=(
                f"Refund: collective goal not reached - {product.name}"
            )[:255],
        )
        result.purchases_refunded += 1

        for grant in grants:
            entitlement_service.expire_entitlement(
                entitlement_id=grant.entitlement_id,
                class_id=class_id,
                target_seat_id=grant.target_seat_id,
                actor_seat_id=actor_seat_id,
                product_id=grant.product_id,
                entitlement_type=grant.entitlement_type,
                acquisition_type=grant.acquisition_type,
                correlation_id=correlation_id,
                payload={
                    "reason": reason,
                    "source": "collective_goal_expiry",
                    # The refund is reachable through this transaction; the
                    # amount is the Ledger's truth and is deliberately not
                    # duplicated here (DOM-STORE-001 §VII.A).
                    "refunded_transaction_id": covering_tx.id,
                },
            )
            result.entitlements_expired += 1

    # A fully resolved unmet goal is terminal at the product level as well:
    # it must stop appearing as sellable, and its now-terminal buy-ins no
    # longer contribute to the live progress projection.
    if not result.unresolved_correlations:
        product.availability_state = "RETIRED"
        product.retired_at = utc_now()

    return result
