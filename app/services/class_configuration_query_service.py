"""
Class Configuration Query Service — Phase 3 Primitives

Authority: DOM-CLASS-001, DOM-CLASS-002, DOM-CLASS-003
Implements: 16 read-only query functions for class configuration domain

Per SPEC-TIME-001: All temporal queries use canonical_temporal_resolver()
Per SPEC-ECON-002: effective_at parameter enables future-law visibility
Per multi-tenancy rules: All queries scoped by class_id (never teacher_id alone)
"""

from bisect import bisect_right
from datetime import datetime, timezone
from typing import Optional

from app.extensions import db
from app.models import (
    ClassEconomy,
    ClassFeature,
    EconomicEngine,
    HallPassSettings,
    PayrollSettings,
    RentSettings,
)
from app.utils.canonical_temporal_resolver import (
    ensure_utc,
    SYSTEM_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


# Advisory thresholds for economic-mode guidance (student-hours per week)
_TIGHT_CAPACITY_CEILING = 500
_DEFAULT_CAPACITY_CEILING = 1500

# Payroll rate guardrails (dollars per hour)
_MAX_HOURLY_PAY_RATE = 100
_TIGHT_MODE_RATE_WARNING = 10
_COMFORTABLE_MODE_RATE_WARNING = 5


def _resolve_query_time(effective_at: Optional[datetime]) -> datetime:
    """Resolve the query timestamp via the canonical temporal resolver (SPEC-TIME-001).

    Args:
        effective_at: Explicit timezone-aware UTC datetime, or None to use canonical now.

    Returns:
        Timezone-aware UTC datetime for query scoping.
    """
    if effective_at is not None:
        return effective_at
    result = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION,
        primitive="current_time"
    )
    return result.canonical_now_utc


# ============================================================================
# 1. CLASS ENTITY QUERIES (1 function)
# ============================================================================


def get_class_economy(class_id: str) -> Optional[ClassEconomy]:
    """Get the ClassEconomy entity for a class.

    Args:
        class_id: The class to retrieve (UUID)

    Returns:
        ClassEconomy instance or None if not found

    Example:
        economy = get_class_economy("abc123-def456")
        if economy:
            print(f"Class: {economy.display_name}, Timezone: {economy.class_timezone}")
    """
    return ClassEconomy.query.filter_by(class_id=class_id).first()


def get_class_economy_by_join_code(join_code: str) -> Optional[ClassEconomy]:
    """Resolve a ClassEconomy from its public join_code alias.

    Used for ingress flows (student claim, add class) where join_code
    is the user-facing identifier. Resolves to class_id authority.

    Args:
        join_code: The user-facing join code string

    Returns:
        ClassEconomy instance or None if not found
    """
    normalized = join_code.strip().upper() if join_code else join_code
    return ClassEconomy.query.filter_by(join_code=normalized).first()


# ============================================================================
# 2. ECONOMIC ENGINE QUERIES — the one effective-at resolver
# ============================================================================
#
# ``economic_engine`` is append-only with an effective date (DOM-CLASS-003
# §VII). Owner ruling 2026-09-30: there is one authoritative answer to "which
# engine version governs this class at instant t", and every reader asks it.
# The class-feature link timeline is not a second answer: a ``class_features``
# row says whether a feature is on, never which engine version is in force.
# ``tests/guards/economic_engine_reads.py`` refuses an ``economic_engine`` read
# anywhere but this module.


def _engine_newest_first(query):
    return query.order_by(
        EconomicEngine.effective_at.desc(),
        EconomicEngine.created_at.desc(),
        EconomicEngine.economic_version_id.desc(),
    )


def economic_engine_effective_at(class_id: str, instant: Optional[datetime]) -> Optional[EconomicEngine]:
    """The Economic Engine version in force for ``class_id`` at ``instant``.

    The version in force is the one with the greatest ``effective_at`` at or
    before ``instant``, the latest ``created_at`` breaking a tie. A version
    whose ``effective_at`` is still ahead is pending and governs nothing yet.
    """
    if not class_id:
        return None
    query_time = _resolve_query_time(instant)
    return _engine_newest_first(
        EconomicEngine.query.filter(
            EconomicEngine.class_id == class_id,
            EconomicEngine.effective_at <= query_time,
        )
    ).first()


def get_current_economic_engine(class_id: str) -> Optional[EconomicEngine]:
    """The Economic Engine version in force now."""
    return economic_engine_effective_at(class_id, None)


class EconomicEngineTimeline:
    """Every version of one class's engine, answering ``at(instant)`` in memory.

    For a reader that resolves many instants at once (daily savings accrual):
    the same rule as ``economic_engine_effective_at``, read from one query
    instead of one per instant.
    """

    def __init__(self, versions):
        # Oldest governing first; among equal effective_at the latest created
        # sorts last, so it wins the bisect exactly as it wins the resolver.
        self.versions = list(reversed(versions))
        self._starts = [ensure_utc(version.effective_at) for version in self.versions]

    def at(self, instant: datetime) -> Optional[EconomicEngine]:
        index = bisect_right(self._starts, ensure_utc(instant)) - 1
        return self.versions[index] if index >= 0 else None


def economic_engine_timeline(class_id: str) -> EconomicEngineTimeline:
    if not class_id:
        return EconomicEngineTimeline([])
    return EconomicEngineTimeline(
        _engine_newest_first(EconomicEngine.query.filter_by(class_id=class_id)).all()
    )


def pending_economic_engines(class_id: str, *, as_of: Optional[datetime] = None) -> list[EconomicEngine]:
    """Engine versions recorded but not yet in force, soonest first.

    For each future effective date only the version that will be in force at
    that date is returned; a pending version superseded before its date stays
    in history but is not a pending change.
    """
    if not class_id:
        return []
    query_time = _resolve_query_time(as_of)
    rows = (
        EconomicEngine.query.filter(
            EconomicEngine.class_id == class_id,
            EconomicEngine.effective_at > query_time,
        )
        .order_by(EconomicEngine.effective_at.asc(), EconomicEngine.created_at.desc())
        .all()
    )
    winners: dict = {}
    for row in rows:
        winners.setdefault(row.effective_at, row)
    return list(winners.values())


def get_economic_engine_by_version(class_id: str, economic_version_id: str) -> Optional[EconomicEngine]:
    """A specific version by its identity, scoped to a class.

    Resolving a frozen reference, not a question of which version is in force.
    """
    return EconomicEngine.query.filter_by(
        economic_version_id=economic_version_id,
        class_id=class_id,
    ).first()


# ============================================================================
# 3. CLASS FEATURE QUERIES (3 functions)
# ============================================================================


def get_class_features(
    class_id: str,
    effective_at: Optional[datetime] = None,
) -> dict[str, ClassFeature]:
    """Get all enabled class features for a class, keyed by feature name.

    Returns the state of features as of effective_at (default: canonical now).
    Only features with a linked economic_version_id are considered enabled.

    Args:
        class_id: The class to retrieve features for (UUID)
        effective_at: Timezone-aware UTC datetime to query feature state at
            (default: canonical now via SPEC-TIME-001)

    Returns:
        Dict mapping feature name -> ClassFeature instance
        Empty dict if class has no enabled features

    Example:
        features = get_class_features(classroom.class_id)
        if 'payroll' in features:
            print(f"Payroll enabled since {features['payroll'].effective_at}")
    """
    query_time = _resolve_query_time(effective_at)

    # Query ALL ClassFeature rows for this class effective at query_time,
    # including disabled rows (economic_version_id IS NULL) so we can
    # determine the latest state per feature.
    latest_subquery = (
        db.session.query(
            ClassFeature.feature,
            db.func.max(ClassFeature.effective_at).label('max_effective_at'),
        )
        .filter(ClassFeature.class_id == class_id, ClassFeature.effective_at <= query_time)
        .group_by(ClassFeature.feature)
        .subquery()
    )
    class_features = (
        db.session.query(ClassFeature)
        .join(latest_subquery, db.and_(
            ClassFeature.feature == latest_subquery.c.feature,
            ClassFeature.effective_at == latest_subquery.c.max_effective_at,
        ))
        .filter(ClassFeature.class_id == class_id)
        .order_by(ClassFeature.feature, ClassFeature.effective_at.desc())
        .distinct(ClassFeature.feature)
        .all()
    )
    latest_by_feature = {feature.feature: feature for feature in class_features}

    return {
        name: row
        for name, row in latest_by_feature.items()
        if row.economic_version_id is not None
    }


def get_class_feature(
    class_id: str,
    feature: str,
    effective_at: Optional[datetime] = None,
) -> Optional[ClassFeature]:
    """Get a specific class feature by name.

    Args:
        class_id: The class (UUID)
        feature: Feature name (e.g., 'payroll', 'hall_pass', 'rent')
        effective_at: Timezone-aware UTC datetime to query at
            (default: canonical now via SPEC-TIME-001)

    Returns:
        ClassFeature instance or None if not found/disabled

    Example:
        payroll_feature = get_class_feature(classroom.class_id, 'payroll')
        if payroll_feature:
            print(f"Payroll effective since {payroll_feature.effective_at}")
    """
    features = get_class_features(class_id, effective_at)
    return features.get(feature)


def get_class_feature_history(class_id: str, feature: str) -> list[ClassFeature]:
    """Get all versions of a specific class feature in chronological order.

    Ordered by effective_at DESC (most recent first). Includes all rows
    (enabled and disabled) for audit trail visibility.

    Args:
        class_id: The class (UUID)
        feature: Feature name

    Returns:
        List of ClassFeature instances (may be empty)

    Example:
        payroll_history = get_class_feature_history(classroom.class_id, 'payroll')
        for version in payroll_history:
            status = "enabled" if version.economic_version_id else "disabled"
            print(f"Payroll {status} from {version.effective_at}")
    """
    return ClassFeature.query.filter_by(
        class_id=class_id,
        feature=feature
    ).order_by(
        ClassFeature.effective_at.desc()
    ).all()


# ============================================================================
# 4. SETTINGS QUERIES (4 functions)
# ============================================================================


def get_payroll_settings(class_id: str) -> Optional[PayrollSettings]:
    """Get payroll configuration for a class.

    Includes pay_rate ($/minute). Note: expected_weekly_hours is a CWI parameter
    on EconomicEngine, not on PayrollSettings — use `get_current_economic_engine`.

    Args:
        class_id: The class (UUID)

    Returns:
        PayrollSettings instance or None

    Example:
        payroll = get_payroll_settings(classroom.class_id)
        if payroll:
            hourly = float(payroll.pay_rate) * 60
            print(f"Rate: ${hourly}/hr")

    ``payroll_settings`` is append-only and effective-dated (DOM-POL-001 §VI.2):
    this is the row in force now, resolved by the one payroll-settings resolver.
    A pending row saved for the next payroll date is not returned until it is in
    force. A payroll event that already exists resolves its own terms and must
    not call this function (DOM-POL-001 §VII).
    """
    from app.services.payroll.settings import current_payroll_setting

    return current_payroll_setting(class_id)


def get_rent_settings(class_id: str) -> Optional[RentSettings]:
    """Get rent configuration for a class.

    Includes rent_amount, due_day_of_month, first_rent_due_date, grace period.

    Args:
        class_id: The class (UUID)

    Returns:
        RentSettings instance or None

    Example:
        rent = get_rent_settings(classroom.class_id)
        if rent:
            print(f"Students owe ${rent.rent_amount} on day {rent.due_day_of_month}")

    ``rent_settings`` is append-only (DOM-POL-001 §VI.1): a class accumulates one
    immutable row per teacher submission, so "the current policy" is the newest
    ``IN_USE`` row, not merely the only row. Ordering is explicit and total —
    ``rent_configured_at`` can collide within a request, so ``id`` breaks the tie —
    because an unordered ``.first()`` here would hand callers a nondeterministic
    historical policy.

    This resolves the policy in force for NEW work. A fact that already exists
    resolves its own row by the ``policy_uuid`` it froze at creation time and must
    not call this function (DOM-POL-001 §VII).
    """
    return (
        RentSettings.query
        .filter_by(class_id=class_id, availability_state='IN_USE')
        .order_by(RentSettings.rent_configured_at.desc(), RentSettings.id.desc())
        .first()
    )


def get_hall_pass_settings(class_id: str) -> Optional[HallPassSettings]:
    """Get hall pass configuration for a class.

    Includes queue_enabled, queue_limit, pass_types.

    Args:
        class_id: The class (UUID)

    Returns:
        HallPassSettings instance or None

    Example:
        hp = get_hall_pass_settings(classroom.class_id)
        if hp:
            print(f"Queue limit: {hp.max_queue_limit}")

    ``hall_pass_settings`` is append-only (DOM-POL-001 §VI.1): every save inserts
    a new immutable row, so "the current policy" is the newest ``IN_USE`` row.
    ``effective_date`` alone is not a total order — two saves inside one request
    share a timestamp — so ``id`` breaks the tie, matching the ordering used by
    the FEAT-side reader in ``app/feats/prod.py``.
    """
    return (
        HallPassSettings.query
        .filter_by(class_id=class_id, availability_state='IN_USE')
        .order_by(HallPassSettings.effective_date.desc(), HallPassSettings.id.desc())
        .first()
    )


# ============================================================================
# 5. CWI & ECONOMIC DERIVED VALUES (2 functions)
# ============================================================================


def calculate_cwi(class_id: str) -> Optional[float]:
    """Calculate the current Classroom Wage Index (CWI) for a class.

    CWI = (pay_rate * 60) * expected_weekly_hours

    pay_rate is stored as $/minute; we convert to $/hour before multiplying
    by expected_weekly_hours to produce the weekly earning reference value.

    The expected_weekly_hours is a teacher-configured reference value representing
    the expected number of hours a student should be active in a week. Actual weekly
    payout varies based on day-to-day student activity, not this reference value.

    Args:
        class_id: The class (UUID)

    Returns:
        CWI as a float ($/week), or None if payroll settings not found

    Example:
        cwi = calculate_cwi(classroom.class_id)
        if cwi:
            print(f"CWI: ${cwi}/week")
    """
    payroll = get_payroll_settings(class_id)
    if not payroll:
        return None

    # expected_weekly_hours is a CWI parameter on EconomicEngine (canonical per DOM-CLASS-002)
    expected_weekly_hours = resolve_expected_weekly_hours(class_id)
    if expected_weekly_hours is None:
        return None

    hourly_rate = float(payroll.pay_rate) * 60
    return hourly_rate * expected_weekly_hours


def resolve_expected_weekly_hours(class_id: str) -> Optional[float]:
    """Return the canonical Economic Engine expected-hours value for payroll."""
    engine = get_current_economic_engine(class_id)
    if engine is None or engine.expected_weekly_hours is None:
        return None
    return float(engine.expected_weekly_hours)


def get_policy_mode(class_id: str, feature: str = 'payroll') -> Optional[str]:
    """Get the current economic policy mode for a class via a feature anchor.

    The mode of the Economic Engine version in force, when ``feature`` is
    enabled. Defaults to the 'payroll' feature, which is always enabled.

    Args:
        class_id: The class (UUID)
        feature: Feature to use as the engine anchor (default: 'payroll')

    Returns:
        Policy mode string ('tight', 'default', 'comfortable') or None
        if the feature is not enabled

    Example:
        mode = get_policy_mode(classroom.class_id)
        if mode == 'tight':
            print("Restricted economy")
    """
    if not is_feature_enabled(class_id, feature):
        return None
    engine = get_current_economic_engine(class_id)
    if not engine:
        return None

    return engine.economy_policy_mode


# ============================================================================
# 6. CONFIGURATION STATE QUERIES (2 functions)
# ============================================================================


def is_feature_enabled(class_id: str, feature: str) -> bool:
    """Check if a specific feature is enabled for a class.

    Returns True if feature has an active ClassFeature row with
    economic_version_id set and effective_at <= canonical now.

    Args:
        class_id: The class (UUID)
        feature: Feature name

    Returns:
        True if enabled, False otherwise

    Example:
        if is_feature_enabled(classroom.class_id, 'payroll'):
            print("Payroll is active")
    """
    return get_class_feature(class_id, feature) is not None


def get_all_classes_by_teacher(teacher_user_id: int) -> list[ClassEconomy]:
    """Get all classes owned by a teacher.

    Ordered by created_at DESC (most recent first).

    Args:
        teacher_user_id: The teacher's User.id

    Returns:
        List of ClassEconomy instances (may be empty)

    Example:
        classes = get_all_classes_by_teacher(teacher_user.id)
        for cls in classes:
            print(f"{cls.display_name} ({cls.join_code})")
    """
    return ClassEconomy.query.filter_by(
        teacher_user_id=teacher_user_id
    ).order_by(
        ClassEconomy.created_at.desc()
    ).all()


def verify_teacher_owns_class(class_id: str, teacher_user_id: int) -> Optional[ClassEconomy]:
    """Verify a teacher owns a specific class and return it.

    Common authorization guard used across admin routes. Returns the
    ClassEconomy if the teacher owns it, None otherwise.

    Args:
        class_id: Class to check ownership of
        teacher_user_id: The teacher's User.id

    Returns:
        ClassEconomy if teacher owns it, None otherwise

    Example:
        class_row = verify_teacher_owns_class(class_id, current_user.id)
        if not class_row:
            abort(403)
    """
    return ClassEconomy.query.filter_by(
        class_id=class_id,
        teacher_user_id=teacher_user_id,
    ).first()


def has_personalized_class(teacher_user_id: int) -> bool:
    """Check if a teacher has at least one class with a display_name set.

    Used for onboarding status checks. Uses an EXISTS-style query
    (returns first match only) for constant-time performance.

    Args:
        teacher_user_id: The teacher's User.id

    Returns:
        True if any class owned by this teacher has a non-null display_name
    """
    return ClassEconomy.query.filter(
        ClassEconomy.teacher_user_id == teacher_user_id,
        ClassEconomy.display_name.isnot(None),
    ).first() is not None


def get_class_by_public_id(class_public_id: str) -> Optional[ClassEconomy]:
    """Resolve a ClassEconomy from its public-facing ID.

    Used in issue/support flows where class_public_id is the external reference.

    Args:
        class_public_id: The public-facing class identifier

    Returns:
        ClassEconomy if found, None otherwise
    """
    return ClassEconomy.query.filter_by(class_public_id=class_public_id).first()


def get_classes_by_public_ids(class_public_ids: list[str]) -> list[ClassEconomy]:
    """Bulk-resolve ClassEconomy rows from a list of public IDs.

    Args:
        class_public_ids: List of public-facing class identifiers

    Returns:
        List of matching ClassEconomy instances
    """
    if not class_public_ids:
        return []
    return ClassEconomy.query.filter(
        ClassEconomy.class_public_id.in_(class_public_ids)
    ).all()


def get_teacher_classes_by_ids(
    teacher_user_id: int, class_ids: list[str]
) -> dict[str, ClassEconomy]:
    """Bulk-fetch ClassEconomy rows owned by a teacher, keyed by class_id.

    Args:
        teacher_user_id: The teacher's User.id
        class_ids: List of class_id values to fetch

    Returns:
        Dict mapping class_id → ClassEconomy for rows owned by this teacher
    """
    if not class_ids:
        return {}
    rows = ClassEconomy.query.filter(
        ClassEconomy.teacher_user_id == teacher_user_id,
        ClassEconomy.class_id.in_(class_ids),
    ).all()
    return {row.class_id: row for row in rows}


# ============================================================================
# 7. TEACHER-FACING CONFIGURATION GUIDANCE (2 functions)
# ============================================================================


def suggest_economic_mode(class_size: int, weekly_hours: float) -> str:
    """Suggest a policy mode based on class context.

    Returns advisory suggestion ("tight", "default", or "comfortable").
    Teachers can override the suggestion.

    Args:
        class_size: Number of students in class
        weekly_hours: Expected earning hours per week

    Returns:
        Suggested policy mode string

    Note:
        This is advisory only. Teachers retain full authority over policy selection.
        Suggestion algorithm considers class size and weekly earning potential.

    Example:
        suggested = suggest_economic_mode(class_size=25, weekly_hours=50)
        print(f"Suggested mode: {suggested}")
    """
    # Simple heuristic: larger classes with more earning hours → more generous economy
    weekly_capacity = class_size * weekly_hours

    if weekly_capacity < _TIGHT_CAPACITY_CEILING:
        return "tight"
    if weekly_capacity < _DEFAULT_CAPACITY_CEILING:
        return "default"
    return "comfortable"


def validate_payroll_rate(hourly_pay_rate: float, policy_mode: str) -> tuple[bool, Optional[str]]:
    """Validate a proposed hourly pay rate for reasonableness.

    Returns (is_valid, warning_message).
    - is_valid=True: rate accepted (may still have advisory warning)
    - is_valid=False: rate violates hard constraint

    Args:
        hourly_pay_rate: Proposed rate
        policy_mode: Class policy mode ('tight', 'default', 'comfortable')

    Returns:
        Tuple of (is_valid: bool, warning: str | None)

    Example:
        is_valid, warning = validate_payroll_rate(hourly_pay_rate=15.0, policy_mode='default')
        if not is_valid:
            print("Rate rejected")
        elif warning:
            print(f"Warning: {warning}")
    """
    # Hard constraints: hourly rate must be positive and reasonable
    if hourly_pay_rate <= 0:
        return False, "Hourly rate must be positive"

    if hourly_pay_rate > _MAX_HOURLY_PAY_RATE:
        return False, f"Hourly rate exceeds ${_MAX_HOURLY_PAY_RATE}/hour maximum"

    # Advisory warnings based on policy mode
    if policy_mode == "tight" and hourly_pay_rate > _TIGHT_MODE_RATE_WARNING:
        return True, f"Tight mode with rate > ${_TIGHT_MODE_RATE_WARNING}/hr may create imbalance"

    if policy_mode == "comfortable" and hourly_pay_rate < _COMFORTABLE_MODE_RATE_WARNING:
        return True, f"Comfortable mode with rate < ${_COMFORTABLE_MODE_RATE_WARNING}/hr may feel restrictive"

    return True, None
