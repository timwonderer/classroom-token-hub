"""POL insurance guards and command; never opens a FEAT or commits."""
from decimal import Decimal, InvalidOperation
from typing import Optional
from uuid import uuid4
from app.extensions import db
from app.models import InsurancePolicy, InsuranceTierGroup
from app.services import insurance_definition_service as defs
from app.services.insurance_policy_service import MARKETING_BADGES
from app.services.policy_reference_service import insurance_recurring_terms_violation

# Canonical insurance taxonomy (SPEC-ECON-003 §4.5).
TRANSACTION = "TRANSACTION"
PRODUCTIVITY = "PRODUCTIVITY"
NON_MONETARY = "NON_MONETARY"
INSURANCE_TYPES = frozenset({TRANSACTION, PRODUCTIVITY, NON_MONETARY})

# Lawful coverage periods (SPEC §4.5.2/§4.5.8). Monthly is normalized downstream
# by covered class-local days / 7; BIWEEKLY / SEMESTER are NOT lawful.
CHARGE_FREQUENCIES = frozenset({"WEEKLY", "MONTHLY"})

# Per-type structural contract (mirrors the ck_insurance_policies_type_subset
# DB backstop). "required" fields MUST be present & non-null; "forbidden"
# fields MUST be absent/null.
#
# waiting_period_days was previously forbidden for TRANSACTION and PRODUCTIVITY,
# citing "SPEC §4.5.3–§4.5.5" -- a section that does not exist in any document
# under docs/. No normative document restricts it to NON_MONETARY; the
# restriction was invented in the same commit that introduced this schema.
# Operator decision 2026-09-21: settable on every type (not necessarily
# enforced on every type -- only NON_MONETARY currently gates claim
# eligibility on it, in FEAT-STOR-003), so it is required only where it is
# actually used and forbidden nowhere.
_TYPE_REQUIRED = {
    TRANSACTION: (
        "reimbursement_percentage",
        "payout_multiple",
        "claims_per_week_equivalent",
        "claim_window_days",
    ),
    PRODUCTIVITY: (
        "reimbursement_percentage",
        "payout_multiple",
        "claimable_dates_per_week_equivalent",
    ),
    NON_MONETARY: (
        "claims_per_week_equivalent",
        "waiting_period_days",
    ),
}
_TYPE_FORBIDDEN = {
    TRANSACTION: (
        "claimable_dates_per_week_equivalent",
    ),
    PRODUCTIVITY: (
        "claims_per_week_equivalent",
        "claim_window_days",
    ),
    NON_MONETARY: (
        "reimbursement_percentage",
        "payout_multiple",
        "claim_window_days",
        "claimable_dates_per_week_equivalent",
    ),
}

# Typed economic fields and their coercion kind.
_DECIMAL_FIELDS = frozenset(
    {
        "premium",
        "reimbursement_percentage",
        "payout_multiple",
        "claims_per_week_equivalent",
        "claimable_dates_per_week_equivalent",
    }
)
_INT_FIELDS = frozenset({"tier_level", "claim_window_days", "waiting_period_days"})
_TEXT_FIELDS = frozenset({"title", "description", "tier_name", "tier_group"})

# All economic (typed) fields that participate in per-type structure.
_ECONOMIC_FIELDS = (
    "reimbursement_percentage",
    "payout_multiple",
    "claims_per_week_equivalent",
    "claim_window_days",
    "claimable_dates_per_week_equivalent",
    "waiting_period_days",
)


class InsuranceContractViolation(Exception):
    """A submission is not a lawful insurance contract (hard/structural failure).

    Raised BEFORE any delegation to FEAT-POL-001, so an unlawful submission never
    reaches the definition store. Recommendation-range overrides are NOT
    violations — only hard bounds and per-type structure are enforced here.
    """


def _coerce_decimal(field: str, value) -> Decimal:
    try:
        result = Decimal(str(value).strip())
        if not result.is_finite():
            raise ValueError
        return result
    except (InvalidOperation, ValueError, AttributeError):
        raise InsuranceContractViolation(f"{field} must be a number, got {value!r}")


def _coerce_int(field: str, value) -> int:
    try:
        # Reject implicit float truncation surprises by round-tripping through str.
        s = str(value).strip()
        if s != "" and Decimal(s) == Decimal(s).to_integral_value():
            return int(Decimal(s))
        raise ValueError
    except (InvalidOperation, ValueError, AttributeError):
        raise InsuranceContractViolation(f"{field} must be a whole number, got {value!r}")


def _validate_and_build_definition(submission: dict) -> dict:
    """Validate hard legality + per-type structure; return the typed definition dict.

    This is the sole legality gate. It enforces exactly the invariants that are
    real contract law (mirroring the DB CHECK backstops), never the advisory
    recommendation ranges. On any hard/structural failure it raises
    :class:`InsuranceContractViolation`; on success it returns a dict whose keys
    are a subset of the POL writable columns.
    """
    if not isinstance(submission, dict):
        raise InsuranceContractViolation("submission must be a dict of typed fields")

    # --- insurance_type (discriminator) -------------------------------------
    raw_type = submission.get("insurance_type")
    insurance_type = (str(raw_type).strip().upper() if raw_type is not None else "")
    if insurance_type not in INSURANCE_TYPES:
        raise InsuranceContractViolation(
            f"insurance_type must be one of {sorted(INSURANCE_TYPES)}, got {raw_type!r}"
        )

    definition: dict = {"insurance_type": insurance_type}

    # --- common: charge_frequency -------------------------------------------
    raw_freq = submission.get("charge_frequency")
    charge_frequency = (str(raw_freq).strip().upper() if raw_freq is not None else "")
    if charge_frequency not in CHARGE_FREQUENCIES:
        raise InsuranceContractViolation(
            f"charge_frequency must be one of {sorted(CHARGE_FREQUENCIES)} "
            f"(BIWEEKLY/SEMESTER are not lawful), got {raw_freq!r}"
        )
    definition["charge_frequency"] = charge_frequency

    # --- common: premium (>= 0) ---------------------------------------------
    if submission.get("premium") in (None, ""):
        raise InsuranceContractViolation("premium is required")
    premium = _coerce_decimal("premium", submission["premium"])
    if premium < 0:
        raise InsuranceContractViolation("premium must be >= 0")
    definition["premium"] = premium

    # --- per-type structural subset -----------------------------------------
    required = _TYPE_REQUIRED[insurance_type]
    forbidden = _TYPE_FORBIDDEN[insurance_type]

    for field in forbidden:
        if submission.get(field) not in (None, ""):
            raise InsuranceContractViolation(
                f"{insurance_type} must not carry {field}"
            )

    for field in required:
        if submission.get(field) in (None, ""):
            raise InsuranceContractViolation(
                f"{insurance_type} requires {field}"
            )

    # --- coerce + hard-bound the economic fields that apply -----------------
    # A field is written when it is REQUIRED for this type (already validated
    # present above), or when it is merely PERMITTED (not forbidden) and the
    # teacher actually supplied a value -- e.g. waiting_period_days on
    # TRANSACTION/PRODUCTIVITY: settable everywhere, required only where a
    # type's own submission gate reads it (NON_MONETARY). Skipping it here for
    # every non-required field silently dropped whatever the teacher typed.
    for field in _ECONOMIC_FIELDS:
        if field in required:
            raw = submission[field]
        elif field not in forbidden and submission.get(field) not in (None, ""):
            raw = submission[field]
        else:
            continue
        if field in _DECIMAL_FIELDS:
            val = _coerce_decimal(field, raw)
        else:
            val = _coerce_int(field, raw)

        # Hard non-negativity (mirrors DB CHECKs).
        if val < 0:
            raise InsuranceContractViolation(f"{field} must be >= 0")
        # Hard reimbursement ceiling (SPEC §4.5: reimbursement ≤ 100%).
        if field == "reimbursement_percentage" and val > 100:
            raise InsuranceContractViolation("reimbursement_percentage must be <= 100")
        definition[field] = val

    # --- recurring billing terms (DOM-POL-001A §V.E) --------------------------
    # Required on every definition: the bill preview interval (strictly inside
    # the shortest period of the cadence, per the resolver), the nonpayment
    # mode, and cancel_after_days iff CANCEL_AFTER_X_DAYS.
    raw_preview = submission.get("bill_preview_days")
    bill_preview_days = (
        None if raw_preview in (None, "") else _coerce_int("bill_preview_days", raw_preview)
    )
    raw_mode = submission.get("nonpayment_mode")
    nonpayment_mode = (str(raw_mode).strip().upper() if raw_mode not in (None, "") else None)
    raw_cancel = submission.get("cancel_after_days")
    cancel_after_days = (
        None if raw_cancel in (None, "") else _coerce_int("cancel_after_days", raw_cancel)
    )
    violation = insurance_recurring_terms_violation(
        charge_frequency=charge_frequency,
        bill_preview_days=bill_preview_days,
        nonpayment_mode=nonpayment_mode,
        cancel_after_days=cancel_after_days,
    )
    if violation is not None:
        raise InsuranceContractViolation(violation)
    definition["bill_preview_days"] = bill_preview_days
    definition["nonpayment_mode"] = nonpayment_mode
    definition["cancel_after_days"] = cancel_after_days

    # --- optional presentation / provenance metadata ------------------------
    if submission.get("tier_level") not in (None, ""):
        tier_level = _coerce_int("tier_level", submission["tier_level"])
        if tier_level < 0:
            raise InsuranceContractViolation("tier_level must be >= 0")
        definition["tier_level"] = tier_level

    for field in _TEXT_FIELDS:
        val = submission.get(field)
        if val not in (None, ""):
            definition[field] = str(val)

    badge = submission.get("marketing_badge")
    if badge not in (None, ""):
        if badge not in MARKETING_BADGES:
            raise InsuranceContractViolation(f"unknown marketing_badge {badge!r}")
        definition["marketing_badge"] = badge

    if submission.get("tier_group_id"):
        from uuid import UUID
        try:
            definition["tier_group_id"] = str(UUID(submission["tier_group_id"]))
        except (ValueError, TypeError, AttributeError):
            raise InsuranceContractViolation("Invalid tier group identity")
    return definition


# Grouped insurance tiers are the three ordinals basic(1)/mid(2)/premium(3). An
# ungrouped (SINGLE) offering carries no ``tier_group_id``. Within one group, at most
# one IN_USE policy may occupy each rank — giving at most three active tiers per
# group (v1 parity). Enforced here as the FEAT-CLASS-003 command-layer guard, with
# a partial unique index (class_id, tier_group_id, tier_level WHERE IN_USE) as a
# concurrent-create backstop.
_GROUPED_TIER_RANKS = (1, 2, 3)


def _enforce_tier_group_rules(class_id: str, definition: dict) -> None:
    """Reject a grouped tier that breaks rank-uniqueness or the 3-per-group cap.

    A grouped policy (``tier_group_id`` set) must carry a rank in {1,2,3} and may not
    duplicate a rank already held by an IN_USE policy in the same group, nor push
    the group past three active tiers. Because definitions are immutable, editing a
    tier means minting a new IN_USE row for that slot — so the prior IN_USE tier at
    that rank must be retired first (the guard counts only IN_USE rows).
    """
    tier_group = definition.get("tier_group_id")
    if tier_group in (None, ""):
        # Ungrouped / SINGLE offering: no group constraints. A bare tier_level is
        # allowed only as a presentation ordinal, carrying no group semantics.
        return

    tier_level = definition.get("tier_level")
    if tier_level not in _GROUPED_TIER_RANKS:
        raise InsuranceContractViolation(
            "a grouped insurance tier requires tier_level of 1 (basic), "
            "2 (mid), or 3 (premium)"
        )

    active = (
        InsurancePolicy.query
        .filter(
            InsurancePolicy.class_id == class_id,
            InsurancePolicy.tier_group_id == tier_group,
            InsurancePolicy.availability_state == defs.IN_USE,
        )
        .all()
    )
    if any(p.tier_level == tier_level for p in active):
        raise InsuranceContractViolation(
            f"tier group '{tier_group}' already has an active tier at level "
            f"{tier_level}; retire it before adding another at the same level"
        )
    if len(active) >= 3:
        raise InsuranceContractViolation(
            f"tier group '{tier_group}' already has the maximum of 3 active tiers"
        )


def create_tier_group(class_id, name):
    if not isinstance(name, str) or not name.strip() or len(name) > 60:
        raise InsuranceContractViolation("A group name of 1–60 characters is required")
    group = InsuranceTierGroup(class_id=class_id, group_id=str(uuid4()), name=name.strip())
    db.session.add(group)
    db.session.flush()
    return group


def submit_insurance_definition(*, class_id, submission, actor_seat_id, availability_state=defs.IN_USE, supersedes_policy_uuid=None):
    definition = _validate_and_build_definition(submission)
    predecessor = None
    if supersedes_policy_uuid:
        predecessor = defs.get_insurance_definition(supersedes_policy_uuid, class_id=class_id)
        if predecessor is None:
            raise defs.InsuranceDefinitionNotFound(supersedes_policy_uuid)
        definition["supersedes_policy_uuid"] = predecessor.policy_uuid
    group_id = definition.get("tier_group_id")
    if group_id:
        group = db.session.get(InsuranceTierGroup, (class_id, group_id))
        if group is None:
            raise InsuranceContractViolation("Tier group not found in this class")
        definition["tier_group"] = group.name
    elif definition.get("tier_group"):
        if definition.get("tier_level") not in _GROUPED_TIER_RANKS:
            raise InsuranceContractViolation("Grouped tier requires tier_level of 1, 2 or 3")
        group = create_tier_group(class_id, definition["tier_group"])
        definition["tier_group_id"] = group.group_id
    if predecessor:
        defs.retire_insurance_definition(policy_uuid=predecessor.policy_uuid, class_id=class_id)
    _enforce_tier_group_rules(class_id, definition)
    return defs.create_insurance_definition(class_id=class_id, definition=definition,
        actor_seat_id=actor_seat_id, availability_state=availability_state)
