"""
Authentication and authorization utilities for Classroom Token Hub.

Contains session management helpers, authentication decorators, and timeout logic.
"""

import urllib.parse
import secrets
from datetime import datetime
from app.utils.canonical_temporal_resolver import canonical_temporal_resolver, SYSTEM_LEVEL_EVALUATION
from functools import wraps

import sqlalchemy as sa
from flask import session, flash, redirect, url_for, request, current_app, jsonify, abort, g
from app.extensions import db
from app.hash_utils import hash_username_lookup
from app.utils.auth_username import normalize_auth_username


# -------------------- SESSION CONFIGURATION --------------------

SESSION_TIMEOUT_MINUTES = 10
# DOM-IDEN-003 §Session Establishment: fixed window from sign-in, never extended by activity.
TEACHER_SESSION_MINUTES = 60
SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES = 60


def _table_exists(table_name: str) -> bool:
    """Return whether the current database exposes the given table."""
    conn = db.session.connection()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    """Return whether the current database exposes the given column on a table."""
    if not _table_exists(table_name):
        return False
    conn = db.session.connection()
    inspector = sa.inspect(conn)
    return any(column.get("name") == column_name for column in inspector.get_columns(table_name))


def _get_safe_next_path() -> str:
    """
    Return a safe relative path that can be used as a `next` parameter.

    Ensures the value is a same-site path without scheme or host to avoid
    open redirect vulnerabilities if used in a subsequent redirect.
    """
    # Start from the Flask path, which is already URL-decoded and does not
    # include the scheme or host for normal requests.
    raw_path = request.path or "/"

    # Normalize any backslashes to forward slashes to avoid browser quirks.
    raw_path = raw_path.replace("\\", "/")

    # Parse the path in case an attacker has tried to smuggle in a scheme
    # or netloc via malformed input.
    parsed = urllib.parse.urlparse(raw_path)

    # Only allow pure paths without scheme or netloc.
    if parsed.scheme or parsed.netloc:
        return "/"

    path = parsed.path or "/"

    # Disallow protocol-relative style (`//evil.com`) paths.
    if path.startswith("//"):
        return "/"

    # Ensure the path is absolute within this application.
    if not path.startswith("/"):
        path = "/" + path

    return path


def _is_grafana_proxy_subrequest() -> bool:
    path = request.path or ""
    return path.startswith("/sysadmin/grafana/") or path == "/sysadmin/grafana/auth-check"


def _expire_system_admin_session():
    session.pop("user_id", None)
    session.pop("current_session_nonce", None)
    session.pop("last_activity", None)
    session.pop("sysadmin_auth_username", None)
    session.pop("passkey_sysadmin_auth_username", None)
    session.pop("force_sysadmin_username_migration", None)


def _session_idle_expired(last_activity, now, timeout_minutes) -> bool:
    """True once more than ``timeout_minutes`` have elapsed since ``last_activity`` (SLE)."""
    deadline = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="shift_timestamp",
        timestamp=last_activity, elapsed_seconds=timeout_minutes * 60,
    ).shifted_timestamp_utc
    return canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="later_than", candidate=now, reference=deadline,
    ).is_later


def _system_admin_timeout_expired(last_activity) -> bool:
    return _session_idle_expired(last_activity, canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="current_time").canonical_now_utc, SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES)


# -------------------- AUTHENTICATION DECORATORS --------------------

def login_required(f):
    """
    Decorator to require student authentication for a route.

    Enforces a strict 10-minute timeout from login time for students.
    Redirects to student.login if not authenticated or session expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app.services.context_resolver import (
            resolve_canonical_context,
            ContextNotEstablished,
            ContextMismatch,
            ContextForbidden,
            ContextInvariantViolation,
        )

        try:
            ctx = resolve_canonical_context()
        except (ContextNotEstablished, ContextMismatch, ContextForbidden):
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "error": "User not logged in or session expired"}), 401
            return redirect(url_for('student.login', next=request.path))
        except ContextInvariantViolation:
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "error": "Please select a class to continue."}), 403
            return redirect(url_for('student.select_class_context'))

        if not ctx or getattr(ctx, "actor_role", None) != "student":
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "error": "User not logged in or session expired"}), 401
            return redirect(url_for('student.login', next=request.path))

        g.canonical_context = ctx

        # Enforce DB-stored session expiry (User.current_session_expires_at)
        from app.models import User
        user = db.session.get(User, ctx.user_id) if ctx.user_id else None
        now = canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="current_time").canonical_now_utc
        if user and user.current_session_expires_at:
            if not canonical_temporal_resolver(
                SYSTEM_LEVEL_EVALUATION, primitive="earlier_than",
                candidate=now, reference=user.current_session_expires_at,
            ).is_earlier:
                session.clear()
                if request.path.startswith('/api/'):
                    return jsonify({"status": "error", "error": "Session expired"}), 401
                flash("Your session has expired. Please log in again.", "info")
                return redirect(url_for('student.login'))

        session['last_activity'] = now.isoformat()
        return f(*args, **kwargs)
    return decorated_function


_CLASSLESS_ADMIN_ENDPOINTS = frozenset({
    'admin.create_new_class',
    'admin.onboarding',
    'admin.onboarding_status',
    'admin.upload_students',
    'admin.onboarding_skip_task',
    'admin.login',
    'admin.logout',
    'admin.account_delete',
    'admin.select_class_context',
    'admin.passkey_register_start',
    'admin.passkey_register_finish',
    'admin.passkey_delete',
    'admin.passkey_resume',
    'admin.passkey_cancel',
    'admin.passkey_settings',
    'admin.passkey_auth_start',
    'admin.passkey_auth_finish',
    'admin.totp_replace_challenge',
    'admin.totp_replace_start',
    'admin.totp_replace_confirm',
    'admin.totp_replace_cancel',
})


def _is_background_request() -> bool:
    """True for fetch/XHR calls, which must not queue flash messages.

    A flash from a background call lands on whatever page the browser shows
    next. The getting-started widget polls onboarding status on every teacher
    page, so signing out while that request is in flight used to plant a
    session error on the login page.
    """
    fetch_mode = (request.headers.get("Sec-Fetch-Mode") or "").lower()
    if fetch_mode and fetch_mode != "navigate":
        return True
    if request.is_json or (request.headers.get("X-Requested-With") or "").lower() == "xmlhttprequest":
        return True
    return False


#: Endpoints a credential-noncompliant teacher may still reach (DOM-IDEN-003 §VII.A: credential
#: maintenance and teacher account destruction; sign-out is not decorated, so it never reaches the
#: gate). Every request ``static/js/passkey.js`` makes on the Security page, and the one endpoint
#: the account-destruction page posts to, is here and nothing else is.
_ADMIN_CREDENTIAL_MAINTENANCE_ENDPOINTS = frozenset({
    'admin.passkey_settings',
    'admin.passkey_register_start',
    'admin.passkey_register_finish',
    'admin.passkey_delete',
    'admin.passkey_resume',
    'admin.passkey_cancel',
    'admin.totp_replace_challenge',
    'admin.totp_replace_start',
    'admin.totp_replace_confirm',
    'admin.totp_replace_cancel',
    'admin.account_delete',
})

#: The sysadmin counterpart: credential maintenance only (a sysadmin has no account-destruction route).
_SYSADMIN_CREDENTIAL_MAINTENANCE_ENDPOINTS = frozenset({
    'sysadmin.passkey_settings',
    'sysadmin.passkey_register_start',
    'sysadmin.passkey_register_finish',
    'sysadmin.passkey_delete',
    'sysadmin.passkey_resume',
    'sysadmin.passkey_cancel',
    'sysadmin.totp_replace_challenge',
    'sysadmin.totp_replace_start',
    'sysadmin.totp_replace_confirm',
    'sysadmin.totp_replace_cancel',
})

_CREDENTIAL_GATE_TABS = {
    'passkey_missing': 'passkeys',
    'totp_noncompliant': 'authenticator',
}


SECURITY_TABS = ('passkeys', 'authenticator')


def security_active_tab() -> str:
    """The Security page tab named by ``?tab=``, restricted to the known tabs (default: passkeys)."""
    tab = request.args.get('tab', '')
    return tab if tab in SECURITY_TABS else SECURITY_TABS[0]


def credential_noncompliance(user_id):
    """The principal's credential noncompliance, read live from the user row, or ``None``.

    Evaluated on every protected request; nothing is stored or cached between requests
    (DOM-IDEN-003 §VII.A). Read-only.
    """
    from app.models import User
    from app.services.credential_lifecycle import CredentialCompliance, credential_compliance

    # populate_existing: the decision is made from the row as the database holds it now, never
    # from a copy this session loaded earlier.
    user = db.session.get(User, user_id, populate_existing=True)
    if user is None:
        return None
    compliance = credential_compliance(user)
    return None if compliance is CredentialCompliance.COMPLIANT else compliance


def _credential_gate_response(user_id, *, maintenance_endpoints, settings_endpoint, background):
    """Refuse a noncompliant principal anything but credential maintenance (DOM-IDEN-003 §VII.A).

    Returns ``None`` to let the request through. A background request gets JSON 403; a navigation is
    sent to the Security tab that fixes the first noncompliance. Writes nothing, so a GET stays pure.
    """
    if request.endpoint in maintenance_endpoints:
        return None
    noncompliance = credential_noncompliance(user_id)
    if noncompliance is None:
        return None
    if background:
        return jsonify(
            status="error",
            error="credential_noncompliant",
            message="Set up your required sign-in credentials before continuing.",
        ), 403
    return redirect(url_for(settings_endpoint, tab=_CREDENTIAL_GATE_TABS[noncompliance.value]))


def teacher_credential_gate_response(user_id):
    """The gate for a teacher principal; ``None`` when the request may proceed."""
    return _credential_gate_response(
        user_id,
        maintenance_endpoints=_ADMIN_CREDENTIAL_MAINTENANCE_ENDPOINTS,
        settings_endpoint='admin.passkey_settings',
        background=_is_background_request(),
    )


def _teacher_session_ended(message):
    if _is_background_request():
        return jsonify(status="error", error="authentication_required", message=message), 401
    flash(message)
    return redirect(url_for('admin.login'))


def _sysadmin_session_ended(message):
    """The sysadmin counterpart of ``_teacher_session_ended``.

    A Grafana sub-request and a fetch/XHR call get JSON 401 (a flash from a background
    call would land on the next page); a navigation gets the flash and the login redirect.
    """
    if _is_grafana_proxy_subrequest() or _is_background_request():
        return jsonify(status="error", error="authentication_required", message=message), 401
    flash(message)
    return redirect(url_for('sysadmin.login', next=request.path))


def admin_required(f):
    """
    Decorator to require admin authentication for a route.

    The fixed session window is enforced by the session hook in create_app().
    Redirects to admin.login if not authenticated or session expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app.services.context_resolver import (
            resolve_canonical_context,
            ContextNotEstablished,
            ContextMismatch,
            ContextForbidden,
            ContextInvariantViolation,
            BoundaryContext
        )

        # The fixed window itself is enforced for every request by the
        # session hook in create_app(); it only marks why the session ended.
        if g.get("teacher_session_expired"):
            return _teacher_session_ended("Your session expired. Please log in again.")
        try:
            ctx = resolve_canonical_context(require_class=False)
        except (ContextNotEstablished, ContextMismatch, ContextForbidden, ContextInvariantViolation):
            return _teacher_session_ended("Your session has ended. Please log in again.")

        if ctx.actor_role != 'teacher':
            return _teacher_session_ended("Your session has ended. Please log in again.")

        # The credential gate runs before the classless-teacher onboarding redirect, so a
        # teacher with no class is still sent to Security rather than to onboarding.
        gated = teacher_credential_gate_response(ctx.user_id)
        if gated is not None:
            return gated

        if isinstance(ctx, BoundaryContext):
            if request.endpoint not in _CLASSLESS_ADMIN_ENDPOINTS:
                return redirect(url_for('admin.onboarding'))

        g.canonical_context = ctx
        return f(*args, **kwargs)
    return decorated_function


def system_admin_required(f):
    """
    Decorator to require system admin authentication for a route.

    Resolves identity via resolve_canonical_context(require_class=False)
    and verifies actor_role == 'sysadmin'. Stores BoundaryContext in
    g.canonical_context. Enforces session timeout based on last activity.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app.services.context_resolver import (
            resolve_canonical_context, BoundaryContext,
            ContextNotEstablished, ContextMismatch, ContextForbidden,
        )
        try:
            ctx = resolve_canonical_context(require_class=False)
        except (ContextNotEstablished, ContextMismatch, ContextForbidden):
            return _sysadmin_session_ended("System administrator access required.")

        if not isinstance(ctx, BoundaryContext) or ctx.actor_role != 'sysadmin':
            return _sysadmin_session_ended("System administrator access required.")

        last_activity = session.get('last_activity')
        now = canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="current_time").canonical_now_utc
        if last_activity:
            # Every writer stores an offset-bearing UTC ISO string, so this parses aware.
            last_activity = datetime.fromisoformat(last_activity)
            if _session_idle_expired(last_activity, now, SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES):
                _expire_system_admin_session()
                return _sysadmin_session_ended("Session expired. Please log in again.")

        g.canonical_context = ctx
        session['last_activity'] = now.isoformat()

        gated = _credential_gate_response(
            ctx.user_id,
            maintenance_endpoints=_SYSADMIN_CREDENTIAL_MAINTENANCE_ENDPOINTS,
            settings_endpoint='sysadmin.passkey_settings',
            background=_is_grafana_proxy_subrequest() or _is_background_request(),
        )
        if gated is not None:
            return gated
        return f(*args, **kwargs)
    # Marks the endpoint as part of the authenticated sysadmin console, so
    # request correlation (app/services/tlcp.py) can name the surface a request
    # asked for from the admission rule itself rather than from a hand-kept list.
    # Diagnostic only: admission is the check above, which keys off the
    # authenticated principal, never off the URL.
    decorated_function.admits_only_system_admin = True
    return decorated_function


# -------------------- HELPER FUNCTIONS --------------------

def is_student_account_active(student):
    """Return True when a student account exists and has not been deleted."""
    return student is not None


def get_logged_in_user():
    """Return the logged-in canonical credential identity, if present."""
    return get_current_user()


def find_canonical_user_by_auth_username(username: str, *, expected_role: str):
    """Return the canonical credential principal for a normalized login name."""
    from app.models import User

    normalized = normalize_auth_username(username)
    if not normalized:
        return None

    user = User.query.filter_by(username_lookup_hash=hash_username_lookup(normalized)).first()
    if not user or getattr(user.user_role, "value", user.user_role) != expected_role:
        return None
    return user


def get_current_student_seat():
    """Return the active seat for the current student session, if present."""
    seat = get_current_seat()
    return seat


def _first_present_session_value(*keys):
    """Return the first non-empty value found in session for the provided keys."""
    for key in keys:
        value = session.get(key)
        if value is not None and value != "":
            return value
    return None


def get_current_seat():
    """
    Return the current Seat from session context.

    Resolution order:
    1) current_seat_id
    Returns None when canonical seat context cannot be resolved safely.
    """
    from app.models import Seat

    if hasattr(g, "_auth_current_seat_cache"):
        return g._auth_current_seat_cache

    context = getattr(g, "_auth_canonical_context_cache", None)
    if context is None:
        try:
            from app.services.context_resolver import resolve_canonical_context

            context = resolve_canonical_context()
        except Exception:
            context = None
        g._auth_canonical_context_cache = context
    if not context:
        return None
    seat = db.session.get(Seat, context.seat_id)
    if seat:
        g._auth_current_seat_cache = seat
    return seat


def get_current_class_id():
    """
    Return current class identifier from canonical request context.
    """
    context = getattr(g, "_auth_canonical_context_cache", None)
    if context is None:
        try:
            from app.services.context_resolver import resolve_canonical_context, ContextResolutionError

            context = resolve_canonical_context()
        except Exception:
            context = None
        g._auth_canonical_context_cache = context
    return getattr(context, "class_id", None) if context else None


def set_canonical_user_session(*, username_lookup_hash: str, expected_role: str):
    """Resolve a User by lookup hash and set session if the role matches."""
    from app.models import User
    user = User.query.filter_by(username_lookup_hash=username_lookup_hash).first()
    if not user:
        return None
    role_value = user.user_role.value if hasattr(user.user_role, "value") else str(user.user_role)
    if role_value != expected_role:
        return None
    session["user_id"] = user.id
    return user


def establish_teacher_session(user):
    """Establish canonical teacher session keys and the fixed 60-minute window (DOM-IDEN-003).

    Caller must hold FEAT-IDEN-009 (identity_service.establish_teacher_session_fields
    owns the row write); this only sets the non-DB Flask session keys and reads
    back what that command wrote onto ``user``.
    """
    from app.session_lifetime import SESSION_EXPIRES_AT_KEY
    from app.services.identity_service import establish_teacher_session_fields

    now = canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="current_time").canonical_now_utc
    expires_at = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="shift_timestamp",
        timestamp=now, elapsed_seconds=TEACHER_SESSION_MINUTES * 60,
    ).shifted_timestamp_utc
    nonce = establish_teacher_session_fields(user, started_at=now, expires_at=expires_at)

    session["user_id"] = user.id
    session["role"] = "admin"
    session["current_session_nonce"] = nonce
    # The cookie dies with the server-side window.
    session[SESSION_EXPIRES_AT_KEY] = expires_at.isoformat()
    session.permanent = True


def end_signed_in_session():
    """Sign the browser out and void its sign-in on the ``users`` row.

    Clearing only the cookie would leave ``current_session_nonce`` valid, so a
    copy of the cookie would keep working (DOM-IDEN-002/003 §Session
    Establishment). The row is cleared only for the sign-in this cookie holds:
    a stale cookie must not end a newer sign-in elsewhere.
    """
    from app.feats.base import FEATContext
    from app.services.identity_service import revoke_signed_in_session
    from app.utils.user_ids import session_user_id

    user_id = session_user_id(session)
    nonce = session.get("current_session_nonce")
    if user_id is not None and nonce:
        with FEATContext("FEAT-IDEN-009", idempotency_key=f"identity:sign-out:{user_id}:{nonce}"):
            revoke_signed_in_session(user_id, nonce)
    session.clear()


def establish_sysadmin_session(user):
    """Establish canonical system-admin session keys.

    Caller must hold FEAT-IDEN-009 (identity_service.establish_sysadmin_session_fields
    owns the row write).
    """
    from app.services.identity_service import establish_sysadmin_session_fields

    nonce = establish_sysadmin_session_fields(user)
    session["user_id"] = user.id
    session["role"] = "sysadmin"
    session["current_session_nonce"] = nonce
    session.permanent = True


def establish_student_session(user, *, class_id: str | None = None, seat_id: int | None = None):
    """Establish canonical student session keys and the fixed session window.

    ``class_id``/``seat_id`` are omitted when login has no valid persisted
    class selection yet; the session is then established class-less, pending
    ``student.select_class_context``.

    Caller must hold FEAT-IDEN-009 (identity_service.establish_student_session_fields
    owns the row write, including the canonical active-class pointers).
    """
    from app.session_lifetime import SESSION_EXPIRES_AT_KEY
    from app.services.identity_service import establish_student_session_fields

    now = canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="current_time").canonical_now_utc
    expires_at = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="shift_timestamp",
        timestamp=now, elapsed_seconds=SESSION_TIMEOUT_MINUTES * 60,
    ).shifted_timestamp_utc
    nonce = establish_student_session_fields(
        user, started_at=now, expires_at=expires_at, class_id=class_id, seat_id=seat_id,
    )

    session["user_id"] = user.id
    session["role"] = "student"
    session["current_session_nonce"] = nonce
    session["login_time"] = now.isoformat()
    session["last_activity"] = now.isoformat()
    session[SESSION_EXPIRES_AT_KEY] = expires_at.isoformat()
    if class_id is not None:
        session["class_id"] = class_id
    session.permanent = True


def get_current_user():
    """
    Return the current User from session/seat context.

    Resolution order:
    1) canonical user_id session key
    Returns None when unavailable.
    """
    from app.models import User

    if hasattr(g, "_auth_current_user_cache"):
        return g._auth_current_user_cache

    from app.utils.user_ids import session_user_id
    user_id = session_user_id(session)
    if user_id:
        user = db.session.get(User, user_id)
        if user:
            g._auth_current_user_cache = user
            return user

    return None


def require_seat_context():
    """
    Return a Seat when valid seat context exists.

    Aborts with HTTP 401 when seat context cannot be resolved.
    """
    seat = get_current_seat()
    if seat:
        return seat
    abort(401)


def switch_student_session_context(student, *, class_id: str, seat_id: int):
    """
    CANONICAL SESSION CONTEXT SWITCH.
    Logs the transition and ensures all session keys are synchronized.
    """
    from flask import session, current_app
    from app.models import User
    
    old_class = getattr(getattr(g, "canonical_context", None), "class_id", None)

    from app.models import Seat

    seat = db.session.get(Seat, seat_id)
    if seat and seat.user_id:
        linked_user = db.session.get(User, seat.user_id)
        if linked_user and (linked_user.last_active_class_id != class_id or linked_user.last_active_seat_id != seat_id):
            from app.services.identity_service import select_student_class_fields
            select_student_class_fields(linked_user, class_id=class_id, seat_id=seat_id)
            db.session.flush()
    
    # Log the transition for audit clarity
    from app.services.tlcp import class_log_ref
    current_app.logger.info(
        "SESSION-CONTEXT-SWITCH: seat %s moved from class %s to %s.",
        seat.public_id if seat else "-", class_log_ref(old_class), class_log_ref(class_id),
    )
    return seat

    # is_viewing_as_student / can_access_student_routes — REMOVED (prohibited feature, cross-account leak risk)
