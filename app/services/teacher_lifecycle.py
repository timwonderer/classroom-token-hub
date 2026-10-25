"""Teacher sign-in retention and terminal account lifecycle (DOM-IDEN-003)."""
from app import db
from app.feats.base import requires_feat_context, generate_correlation_id
from app.models import User
from app.services.context_resolver import BoundaryContext
from app.utils.canonical_temporal_resolver import SYSTEM_LEVEL_EVALUATION, canonical_temporal_resolver

# Elapsed-time retention windows (DOM-IDEN-003), in exact seconds.
SIGNED_IN_RETENTION_SECONDS = 180 * 24 * 60 * 60
NEVER_SIGNED_IN_RETENTION_SECONDS = 30 * 24 * 60 * 60


def record_teacher_sign_in(user_id):
    """Called only after successful authentication, inside its FEAT transaction."""
    user = User.query.filter_by(id=user_id, user_role="teacher").populate_existing().with_for_update().one()
    user.last_signed_in_at = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="current_time",
    ).canonical_now_utc
    return user


def teacher_account_is_stale(user, now):
    if user is None or user.user_role != "teacher":
        return False
    if user.last_signed_in_at is not None:
        anchor, window = user.last_signed_in_at, SIGNED_IN_RETENTION_SECONDS
    elif user.created_at is not None:
        anchor, window = user.created_at, NEVER_SIGNED_IN_RETENTION_SECONDS
    else:
        return False
    cutoff = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="shift_timestamp", timestamp=now, elapsed_seconds=-window,
    ).shifted_timestamp_utc
    # Stale once the anchor is at or before the cutoff (anchor <= now - window).
    return not canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="later_than", candidate=anchor, reference=cutoff,
    ).is_later


@requires_feat_context("FEAT-IDEN-007")
def destroy_stale_teacher(*, user_id, correlation_id, idempotency_key):
    # Successful sign-in uses the same lock. Re-evaluate after waiting: a stale
    # candidate list never authorizes deletion of a teacher who just signed in.
    user = User.query.filter_by(id=user_id, user_role="teacher").populate_existing().with_for_update().one_or_none()
    now = canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="current_time").canonical_now_utc
    if not teacher_account_is_stale(user, now):
        return False
    from app.services.teacher_destruction import _destroy_teacher_account_rows
    _destroy_teacher_account_rows(
        canonical_context=BoundaryContext(user_id=user.id, actor_role="teacher"),
        admin_user=user,
    )
    return True


def purge_stale_teacher_accounts():
    import logging
    now = canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="current_time").canonical_now_utc
    signed_in_cutoff = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="shift_timestamp",
        timestamp=now, elapsed_seconds=-SIGNED_IN_RETENTION_SECONDS,
    ).shifted_timestamp_utc
    never_signed_in_cutoff = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="shift_timestamp",
        timestamp=now, elapsed_seconds=-NEVER_SIGNED_IN_RETENTION_SECONDS,
    ).shifted_timestamp_utc
    ids = [user_id for (user_id,) in db.session.query(User.id).filter(
        User.user_role == "teacher",
        db.or_(User.last_signed_in_at <= signed_in_cutoff,
               db.and_(User.last_signed_in_at.is_(None), User.created_at <= never_signed_in_cutoff)),
    ).all()]
    deleted = 0
    for user_id in ids:
        try:
            deleted += bool(destroy_stale_teacher(
                user_id=user_id, correlation_id=generate_correlation_id(),
                idempotency_key=f"identity:stale-teacher:{user_id}",
            ))
        except Exception:
            db.session.rollback()
            logging.getLogger(__name__).exception("Teacher lifecycle destruction failed for user_id=%s", user_id)
    return deleted
