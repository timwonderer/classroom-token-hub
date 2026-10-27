"""Identity-owned export authority. Callers hold its lock until transaction end."""
import secrets
from flask import has_request_context, request, session
from app.extensions import db
from app.models import User, Seat, UserRole
from app.services.configuration_artifact import ConfigurationError, digest, instant
from app.utils.canonical_temporal_resolver import SYSTEM_LEVEL_EVALUATION, canonical_temporal_resolver


def execution_authority(context, session_nonce, *, lock):
    query = User.query.filter_by(id=context.user_id).populate_existing()
    user = (query.with_for_update() if lock else query).first()
    if (user is None or user.user_role != UserRole.TEACHER or context.actor_role != "teacher"
            or not session_nonce or not secrets.compare_digest(user.current_session_nonce or "", session_nonce)):
        raise ConfigurationError("Your authorization has changed. Sign in again.")
    if has_request_context() and request.blueprint == "configuration":
        from app.auth import _session_idle_expired, SESSION_TIMEOUT_MINUTES
        last_activity = session.get("last_activity")
        if not last_activity or _session_idle_expired(instant(last_activity), now(), SESSION_TIMEOUT_MINUTES):
            raise ConfigurationError("Your session expired. Sign in again.")
    return user


def assert_actor_seat(context):
    seat = Seat.query.filter_by(id=context.seat_id, class_id=context.class_id,
                               user_id=context.user_id, role="teacher").populate_existing().first()
    if seat is None:
        raise ConfigurationError("You must hold the teacher seat in this class")


def now():
    return canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="current_time").canonical_now_utc


def new_export_reference():
    reference = secrets.token_hex(32)
    issued = now()
    expires = canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="shift_timestamp",
        timestamp=issued, elapsed_seconds=5 * 86400).result["shifted_timestamp_utc"]
    return reference, issued.isoformat(), expires.isoformat()


def rotate(user, reference, expires):
    user.configuration_export_verifier = digest(reference)
    user.configuration_export_expires_at = instant(expires)
    db.session.flush()


def validate_reference(user, envelope, token=None):
    current = now()
    expires = instant(envelope["expires_at"])
    if (not secrets.compare_digest(user.configuration_export_verifier or "", digest(envelope["reference"]))
            or user.configuration_export_expires_at is None
            or not canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="same_instant",
                candidate=expires, reference=user.configuration_export_expires_at).is_same
            or not canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="earlier_than",
                candidate=current, reference=expires).is_earlier):
        raise ConfigurationError("This export has expired or has been replaced")
    if token is not None and not canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION, primitive="earlier_than", candidate=current,
            reference=instant(token["expires_at"])).is_earlier:
        raise ConfigurationError("This confirmation has expired")
