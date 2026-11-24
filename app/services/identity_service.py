"""Identity-owned principal provisioning and canonical User/Seat resolution."""

from __future__ import annotations

import pyotp

import secrets

from app.extensions import db
from app.feats.base import get_active_feat_name
from app.models import ClassEconomy, Seat, User, UserRole
from app.utils.auth_username import build_hashed_username_fields, normalize_auth_username
from app.utils.encryption import encrypt_totp


def _require_feat(*feat_names: str) -> None:
    active = get_active_feat_name()
    if active not in feat_names:
        wanted = feat_names[0] if len(feat_names) == 1 else f"one of {feat_names!r}"
        raise PermissionError(
            f"Identity session command requires {wanted}, active={active!r}."
        )


def create_system_principal(username: str) -> str | None:
    """Identity-owned authentication material for the operator bootstrap."""
    if get_active_feat_name() != "FEAT-IDEN-008":
        raise PermissionError("System principal creation requires FEAT-IDEN-008.")
    username = normalize_auth_username(username)
    if not username:
        raise ValueError("Username is required.")

    _, username_hash, lookup_hash = build_hashed_username_fields(username)
    if User.query.with_entities(User.id).filter_by(username_lookup_hash=lookup_hash).first() is not None:
        return None
    secret = pyotp.random_base32()
    db.session.add(User(
        user_role=UserRole.SYSADMIN,
        username_hash=username_hash,
        username_lookup_hash=lookup_hash,
        totp_secret_encrypted=encrypt_totp(secret),
    ))
    db.session.flush()
    return secret


def resolve_teacher_seat_for_class(class_id: str) -> Seat:
    """Resolve the canonical teacher seat for an explicit class scope.

    This is the Identity-owned operation for scheduled/system transitions. It
    validates the class owner binding and the class-local teacher seat instead
    of selecting an arbitrary teacher row. Request-time callers must continue
    to use ``CanonicalContext`` (INV-ARC-001, INV-ARC-008).
    """
    if not class_id:
        raise ValueError("FATAL: class_id is required to resolve teacher seat.")

    class_row = db.session.get(ClassEconomy, class_id)
    if class_row is None or not class_row.teacher_user_id:
        raise ValueError(f"FATAL: No established teacher owner for class_id={class_id}.")

    teacher_seats = (
        Seat.query
        .filter(
            Seat.class_id == class_id,
            Seat.user_id == class_row.teacher_user_id,
            Seat.role == "teacher",
        )
        .order_by(Seat.id.asc())
        .all()
    )
    if len(teacher_seats) != 1:
        raise ValueError(
            f"FATAL: Expected exactly one canonical teacher seat for class_id={class_id}."
        )
    return teacher_seats[0]

# Removed: ``_resolve_seat(identity, seat=None)``. Given a ``User`` it returned
# ``Seat.query.filter(Seat.user_id == ...).order_by(Seat.id.asc()).first()`` —
# the lowest-id seat across every class the user participates in, with no
# ``class_id`` filter. Under DOM-IDEN-001 §VI a ``User`` holds one ``Seat`` per
# ``Class``, so "the seat for a user" is not a well-formed question: without a
# class it silently answers with whichever class the user joined first. It had
# no callers, so rather than re-express the same unanswerable question with a
# class argument, it is deleted. Callers that need a seat must resolve it from
# a canonical context that already carries ``class_id``.


def get_enrolled_student_seat_ids(class_id: str) -> list[int]:
    """Return the enrolled student seat ids for a class, ascending.

    Read-only Identity-domain surface consumed by the Interpretation domain
    (SPEC-ITR-001 §5.3, §6.4: "enrollment status during the window") as the
    denominator population for class-aggregate observations. Enrollment is
    expressed by the existence of a claimed student ``Seat`` bound to the
    class; ``block``/``period`` is never a scoping key (INV-ARC-019).

    This is deliberately a pure read (no writes, INV-ARC-007) and performs no
    time-windowing: a seat is enrolled for the class, not for a sub-interval.
    """
    if not class_id:
        return []
    rows = (
        Seat.query
        .with_entities(Seat.id)
        .filter(
            Seat.class_id == class_id,
            Seat.role == "student",
            Seat.claimed_at.isnot(None),
        )
        .order_by(Seat.id.asc())
        .all()
    )
    return [row.id for row in rows]


def match_hall_pass_profiles(*, class_id: str, first_name: str, last_name: str):
    """Read-only name matching after the caller establishes class/capability scope."""
    from app.hash_utils import normalize_lookup_text
    from app.models import IdentityProfile

    if not class_id:
        raise ValueError("class_id is required for hall-pass verification")

    def normalize(value):
        return normalize_lookup_text(value or "", kind="name")

    first, last = normalize(first_name), normalize(last_name)
    if not first or not last:
        return []
    profiles = (
        IdentityProfile.query.join(Seat, Seat.id == IdentityProfile.seat_id)
        .filter(
            IdentityProfile.class_id == class_id,
            Seat.class_id == class_id,
            Seat.role == "student",
            Seat.user_id.isnot(None),
            Seat.claimed_at.isnot(None),
        )
    )
    matches = []
    for profile in profiles.yield_per(100):
        if normalize(profile.first_name) == first and normalize(profile.last_name) == last:
            matches.append({"seat_id": profile.seat_id, "display_name": profile.full_name})
            if len(matches) == 2:
                break
    return matches


def resolve_teacher_target_seat(*, ctx, target_seat_id):
    """Pure Identity proof of canonical teacher and class-local student anchors."""
    if (ctx is None or getattr(ctx, 'actor_role', None) != 'teacher'
            or not getattr(ctx, 'class_id', None) or not getattr(ctx, 'seat_id', None)):
        raise ValueError('UNAUTHORIZED_SCOPE')
    actor = Seat.query.filter_by(id=ctx.seat_id, class_id=ctx.class_id,
        user_id=ctx.user_id, role='teacher').first()
    target = Seat.query.filter_by(id=target_seat_id, class_id=ctx.class_id, role='student').first()
    if actor is None or target is None:
        raise ValueError('UNAUTHORIZED_SCOPE')
    return target


# ---------------------------------------------------------------------------
# FEAT-IDEN-009: Identity Session Lifecycle
#
# Establishment, class selection and revocation of a sign-in, for all three
# roles, as one lifecycle under one contract (#1777). These commands own the
# ``users`` row writes (``current_session_nonce``, ``current_session_started_at``,
# ``current_session_expires_at``, ``last_active_class_id``, ``last_active_seat_id``)
# that FEAT-IDEN-001 (read-only, no authenticated principal, DOM-IDEN-005 §VII)
# cannot lawfully own. Callers (app.auth, the route layer) decide *when* to
# call these; the policy of *what* gets written lives here.
# ---------------------------------------------------------------------------

def establish_teacher_session_fields(user: User, *, started_at, expires_at) -> str:
    """Write the teacher's fixed session window and a fresh nonce (DOM-IDEN-003).

    ``started_at``/``expires_at`` are supplied by the caller (computed through
    ``canonical_temporal_resolver``, SPEC-TIME-001) rather than decided here:
    this command owns *that* the window is written atomically with the nonce,
    not the clock read itself.
    """
    _require_feat("FEAT-IDEN-009")
    nonce = secrets.token_urlsafe(32)
    user.current_session_started_at = started_at
    user.current_session_expires_at = expires_at
    user.current_session_nonce = nonce
    return nonce


def establish_sysadmin_session_fields(user: User) -> str:
    """Write a fresh sign-in nonce for a sysadmin. No DB-stored expiry: the
    sysadmin window is idle-timeout-based and tracked in the signed cookie
    (``app.auth.SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES``), not on the row."""
    _require_feat("FEAT-IDEN-009")
    nonce = secrets.token_urlsafe(32)
    user.current_session_nonce = nonce
    return nonce


def establish_student_session_fields(
    user: User, *, started_at, expires_at, class_id: str | None = None, seat_id: int | None = None,
) -> str:
    """Write the student's fixed session window and a fresh nonce.

    ``class_id``/``seat_id`` are omitted when login has no valid persisted
    class selection yet (the session is established in a class-less state
    pending ``student.select_class_context``) — only the sign-in fields are
    written in that case, matching the existing established behavior.
    """
    _require_feat("FEAT-IDEN-009")
    nonce = secrets.token_urlsafe(32)
    user.current_session_started_at = started_at
    user.current_session_expires_at = expires_at
    user.current_session_nonce = nonce
    if class_id is not None and seat_id is not None:
        user.last_active_class_id = class_id
        user.last_active_seat_id = seat_id
    return nonce


def select_student_class_fields(user: User, *, class_id: str, seat_id: int) -> None:
    """Move an already-authenticated student's canonical active-class pointers.

    Unlike establishment, this does not rotate the sign-in nonce: the existing
    session is simply repointed at a different already-bound Seat.

    Callable under FEAT-IDEN-009 (an explicit class switch: ``select_class_context``,
    ``switch_class``) or FEAT-IDEN-005 (activating a class a student just bound via
    ``add_class`` — the pointer move is the last step of that same bind, not a
    separate switch).
    """
    _require_feat("FEAT-IDEN-009", "FEAT-IDEN-005")
    user.last_active_class_id = class_id
    user.last_active_seat_id = seat_id


def select_teacher_class_fields(user: User, *, class_id: str, seat_id: int) -> None:
    """Move an already-authenticated teacher's canonical active-class pointers."""
    _require_feat("FEAT-IDEN-009")
    user.last_active_class_id = class_id
    user.last_active_seat_id = seat_id


def revoke_signed_in_session(user_id, nonce: str) -> bool:
    """Void the sign-in on ``users`` for exactly the session ``nonce`` names.

    Locked (``FOR UPDATE``) and nonce-conditional: a stale or replayed
    revocation must not end a newer sign-in that has since replaced the
    nonce (DOM-IDEN-002/003 §Session Establishment). Returns whether this
    call actually voided a row (``False`` means a newer sign-in already
    holds a different nonce, or the user no longer exists).
    """
    _require_feat("FEAT-IDEN-009")
    if not nonce:
        return False
    user = User.query.filter_by(id=user_id).with_for_update().one_or_none()
    if user is None or user.current_session_nonce != nonce:
        return False
    user.current_session_nonce = None
    user.current_session_expires_at = None
    return True
