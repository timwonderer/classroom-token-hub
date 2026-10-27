"""
FEAT-CLASS-003: Insurance Policy Management (orchestration boundary).

This FEAT is the *orchestrator* of the teacher-directed insurance-policy action.
It is deliberately thin on economics: it does NOT reimplement the Economic Engine
and it does NOT persist definition rows itself. Its whole job is to decide
**lawfulness** and then coordinate the write:

    Teacher submission
        → FEAT-CLASS-003 resolves canonical class/teacher context
        → asks the Economic Engine for recommendation metadata (advisory only)
        → validates ONLY actual contract legality (hard bounds + per-type
          structural subset), allowing values outside recommended ranges
        → delegates the immutable definition write to FEAT-POL-001
        → returns the fresh ``policy_uuid`` row.

Three-layer separation (authority):
- Economic Engine (SPEC-ECON-003): computes recommendations / derived
  consequences / exposes hard bounds. Advisory; enforces nothing at write time.
- FEAT-CLASS-003 (this module, DOM-CLASS spec §VII): decides lawfulness. Allows
  out-of-recommendation-range teacher values; rejects hard-bound and
  type-structure violations; coordinates the write. SHALL NOT mutate policy
  definitions directly — it invokes the POL definition commands within its own
  single FEAT context.
- POL definition commands (``insurance_definition_service.create_insurance_definition``
  / ``set_availability``): persist the already-lawful immutable definition; do not
  reinterpret it. (No FEAT-POL-001 executor exists — a FEAT never executes another
  FEAT; it composes domain commands.)

Immutability (DOM-POL-001): ``policy_uuid`` IS the version. "New" and "edit" both
produce a *fresh* ``policy_uuid`` row; a prior definition is never mutated in place.
Only the availability projection (IN_USE / HIDDEN / RETIRED) may change on an
existing row, via ``set_insurance_definition_availability``.

The ``insurance_policies`` table is the only insurance definition store; there
is no separate version table and no fallback to one.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import InsurancePolicy, Seat
from app.services import insurance_definition_service as defs
from app.services import economic_engine as ee
from app.services.insurance_policy_service import MARKETING_BADGES
from app.services.policy_reference_service import insurance_recurring_terms_violation


from app.services.insurance_configuration import (
    InsuranceContractViolation, _validate_and_build_definition, _enforce_tier_group_rules,
    submit_insurance_definition, INSURANCE_TYPES,
)

def _require_teacher_scope(canonical_context, class_id: str) -> None:
    """Fail closed unless ``canonical_context`` is a lawful teacher actor for ``class_id``.

    Canonical context is MANDATORY on every insurance-policy-management action.
    FEAT-CLASS-003 establishes lawfulness *independently* — it does not trust that
    an upstream admin route already performed these checks. Any missing anchor,
    class mismatch, non-teacher role, or a seat that is not the lawful teacher
    actor for the requested class raises :class:`InsuranceContractViolation`
    BEFORE any delegation to FEAT-POL-001.

    Required canonical anchors: ``user_id``, ``class_id``, ``seat_id``,
    ``actor_role``. The seat must exist, belong to the requested class, carry the
    ``teacher`` role, and be owned by the context user.
    """
    if canonical_context is None:
        raise InsuranceContractViolation("Canonical context is required")

    # Required anchors must all be present.
    user_id = getattr(canonical_context, "user_id", None)
    ctx_class_id = getattr(canonical_context, "class_id", None)
    seat_id = getattr(canonical_context, "seat_id", None)
    actor_role = getattr(canonical_context, "actor_role", None)
    if not user_id:
        raise InsuranceContractViolation("Missing canonical user_id")
    if not ctx_class_id:
        raise InsuranceContractViolation("Missing canonical class_id")
    if not seat_id:
        raise InsuranceContractViolation("Missing canonical seat_id")
    if not actor_role:
        raise InsuranceContractViolation("Missing canonical actor_role")

    # Context class must match the requested class (fail-closed cross-class guard).
    if ctx_class_id != class_id:
        raise InsuranceContractViolation(
            f"Class scope mismatch: context {ctx_class_id} != target {class_id}"
        )

    # Only teachers may manage insurance policies.
    if actor_role != "teacher":
        raise InsuranceContractViolation(
            "Only teachers may manage insurance policies"
        )

    # The seat must be the lawful teacher actor for this class.
    teacher_seat = db.session.get(Seat, seat_id)
    if teacher_seat is None:
        raise InsuranceContractViolation("Canonical seat not found")
    if teacher_seat.class_id != class_id:
        raise InsuranceContractViolation("Teacher seat is not in the requested class")
    if getattr(teacher_seat, "role", None) != "teacher":
        raise InsuranceContractViolation("Canonical seat is not a teacher seat")
    if teacher_seat.user_id != user_id:
        raise InsuranceContractViolation(
            "Canonical seat is not owned by the context user"
        )


def recommend_insurance_terms(
    *,
    class_id: str,
    insurance_type: str,
    tier: str = ee.SINGLE,
    coverage_period: str = "weekly",
    covered_calendar_days: Optional[int] = None,
):
    """Advisory recommendation metadata from the Economic Engine (read-only).

    Wraps ``economic_engine.resolve_insurance``. The result is ADVISORY: teachers
    may lawfully configure values outside the returned ``recommended_ranges``.
    FEAT-CLASS-003 never enforces these ranges — only the hard bounds surfaced in
    ``hard_bounds`` (and the DB CHECK backstops) are law. No FEAT context needed:
    this performs no mutation.
    """
    product = str(insurance_type).strip().upper()
    if product not in INSURANCE_TYPES:
        raise InsuranceContractViolation(
            f"insurance_type must be one of {sorted(INSURANCE_TYPES)}, got {insurance_type!r}"
        )
    return ee.resolve_insurance(
        class_id=class_id,
        product=product,
        tier=tier,
        coverage_period=coverage_period,
        covered_calendar_days=covered_calendar_days,
    )


@requires_feat_context("FEAT-CLASS-003")
def configure_insurance_definition(*, class_id, submission, canonical_context,
        actor_seat_id=None, availability_state=defs.IN_USE, supersedes_policy_uuid=None,
        correlation_id=None, idempotency_key=None):
    _require_teacher_scope(canonical_context, class_id)
    return submit_insurance_definition(class_id=class_id, submission=submission,
        actor_seat_id=actor_seat_id or canonical_context.seat_id,
        availability_state=availability_state, supersedes_policy_uuid=supersedes_policy_uuid)


@requires_feat_context("FEAT-CLASS-003")
def set_insurance_definition_availability(
    *,
    class_id: str,
    policy_uuid: str,
    availability_state: str,
    canonical_context,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> InsurancePolicy:
    """Change ONLY the availability projection of an existing definition.

    Economic/identity fields are never touched (no new ``policy_uuid``). Used for
    deactivate (HIDDEN) and retire (RETIRED). Class-scoped + fail-closed via the
    underlying mechanism; delegates to FEAT-POL-001.

    ``canonical_context`` is MANDATORY: teacher/class scope is established
    independently here (missing/invalid context fails closed) before the write.

    Invokes the POL **domain command** (``insurance_definition_service.set_availability``)
    inside this FEAT's single context — it does NOT execute FEAT-POL-001 (no
    FEAT-to-FEAT execution; INV-ARC-000, INV-ARC-021).
    """
    _require_teacher_scope(canonical_context, class_id)

    return defs.set_availability(
        class_id=class_id,
        policy_uuid=policy_uuid,
        availability_state=availability_state,
    )
