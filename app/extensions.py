"""
Shared Flask extension instances.

Centralized to avoid circular imports. Extensions are initialized
here but configured in create_app().
"""

import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from apscheduler.schedulers.background import BackgroundScheduler
# TODO: [DEPENDABOT PR #648] Flask-Limiter 4.x introduces breaking changes:
# - 'default_limits' renamed to 'default_limits_per_method'
# - Decorator syntax may have changed for exempt routes
# - See https://flask-limiter.readthedocs.io/en/stable/changelog.html
# Review before upgrading from 3.5.0 to 4.1.1
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize extensions (without binding to an app yet)
db = SQLAlchemy()
migrate = Migrate(compare_type=True)
csrf = CSRFProtect()
scheduler = BackgroundScheduler()

# Initialize rate limiter
# Uses Cloudflare-aware IP detection for accurate rate limiting
def get_real_ip_for_limiter():
    """Get real IP for rate limiting, handling Cloudflare proxy."""
    try:
        from flask import request
        from app.utils.ip_handler import peer_is_trusted_proxy

        # Forwarding headers are client-typed unless our own reverse proxy
        # wrote them. A connection from any other peer is keyed by its own
        # address, so rotating CF-Connecting-IP / X-Forwarded-For cannot reset
        # a limit (audit S7).
        if not peer_is_trusted_proxy():
            return request.remote_addr or "unknown"
        # Check Cloudflare header first
        real_ip = request.headers.get('CF-Connecting-IP')
        if real_ip:
            return real_ip
        # Fallback to X-Forwarded-For
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        # Final fallback to remote_addr
        return request.remote_addr
    except RuntimeError:
        return get_remote_address()


def _seat_or_ip_limit_key():
    """Key on ``(class_id, seat_id)`` from ``g.canonical_context`` when present.

    Students in a school leave through a small pool of shared public
    addresses, so an address-keyed budget is spent by whoever else sits behind
    the same address. Reads only ``g.canonical_context`` -- never resolves
    context itself (DOM-IDEN-006 §IX) and reads neither the session nor the
    database -- so it is meaningful only where that context is already
    attached and trustworthy by the time the limiter's key func runs. Falls
    back to the address key otherwise, and the key is never empty:
    Flask-Limiter skips a limit whose key is empty.
    """
    from flask import g

    context = getattr(g, "canonical_context", None)
    class_id = getattr(context, "class_id", None)
    seat_id = getattr(context, "seat_id", None)
    if class_id and seat_id:
        return f"seat:{class_id}:{seat_id}"
    return f"ip:{get_real_ip_for_limiter() or 'unknown'}"


def student_status_seat_limit_key():
    """Key the student status poll by seat, not by network address.

    The poll is authenticated, class-scoped activity: its budget belongs to
    ``(class_id, seat_id)``. Meaningful only on a limit decorator placed
    *below* ``@login_required``, which is what leaves a validated context on
    ``g`` for :func:`_seat_or_ip_limit_key` to read.
    """
    return _seat_or_ip_limit_key()


def attendance_tap_seat_limit_key():
    """Key ``/api/tap`` by ``(class_id, seat_id)``, not by network address.

    Audit O1: a shared school address pooled every student's tap budget
    together, so one busy bell-time minute could exhaust the limit for every
    classmate behind the same address. Unlike the student-status poll, this
    route carries no ``@login_required``; the context it reads was still
    resolved for every request by the app-wide ``before_request`` hook
    (``capture_correlation_context`` in ``app/__init__.py``), which runs
    before any route decorator, including this one. An unauthenticated or
    malformed request -- no resolved context -- falls back to the address key,
    which is exactly the traffic an address-keyed limit is still meant to
    bound.
    """
    return _seat_or_ip_limit_key()


def student_login_identity_limit_key():
    """Key a student login attempt by the submitted username, not address.

    Audit O1: student login's address-keyed limit counted GET page loads and
    POST attempts together, and a school NAT shares one address across every
    student in the building, so the whole school drew on one pool. The route
    now scopes its address-keyed limit to POST only (the GETs that render the
    form no longer spend it), and this second limit is what actually bounds
    repeated guessing against ONE account, independent of how many other
    students share the same address.

    Reads the raw submitted username -- a bad or unknown username must still
    count, so this never looks it up -- and hashes it the same way login
    lookups are keyed (``hash_username_lookup``, PEPPER_KEY-derived) so no
    plaintext username is ever written into the limiter's storage. Falls back
    to the address key when no username was submitted (e.g. a GET), and the
    key is never empty: Flask-Limiter skips a limit whose key is empty.
    """
    from flask import request
    from app.hash_utils import hash_username_lookup

    username = (request.form.get("username") or "").strip()
    if username:
        return f"login-identity:{hash_username_lookup(username)}"
    return f"ip:{get_real_ip_for_limiter() or 'unknown'}"


def login_account_limit_key(form_field: str = "username"):
    """Build a per-account rate-limit key from a login POST's username field.

    A limit keyed only by IP (the existing ``10 per minute`` on the teacher
    and sysadmin login routes) does not budget a single account: many guesses
    against one teacher's TOTP code can be spread across source addresses, or
    simply outlast a shared-IP budget shared with other legitimate traffic
    (audit S5). This key is independent of that IP limit, scoped to the
    account rather than the caller, and intentionally coarser (SPEC-SEC-001's
    unsalted lookup digest, not the salted credential hash) since it only
    needs to recognize "the same account was just tried", not authenticate
    anyone.

    Returns a digest, never the raw username, since Flask-Limiter's storage
    keys are visible to anything that can read the limiter's backing store.
    The existing per-IP limit on these routes already covers a request that
    posts no parseable username, so this key is left empty in that case
    rather than guessing a fallback -- Flask-Limiter skips a limit whose key
    is empty.
    """
    from flask import request

    from app.hash_utils import hash_username_lookup
    from app.utils.auth_username import normalize_auth_username

    def _key() -> str:
        normalized = normalize_auth_username(request.form.get(form_field, ""))
        if not normalized:
            return ""
        return f"acct:{hash_username_lookup(normalized)}"

    return _key


def login_totp_replay_limit_key(username_field: str = "username", code_field: str = "totp_code"):
    """Key that lets a given TOTP code be submitted only once per account.

    ``valid_window=1`` on the teacher and sysadmin logins accepts a code for
    up to three 30-second steps, so a captured code is otherwise usable
    again for up to ~90 seconds after the legitimate login (audit S5). This
    pairs a ``1 per 2 minutes`` limit (comfortably past that window) with a
    key scoped to this exact (account, code) pair, so resubmitting the same
    code -- whether a replay or a double-submitted form -- is refused, while
    a different code (a genuine retry after a typo) gets its own budget.

    Left empty (and so skipped by Flask-Limiter) when either field is
    missing, rather than falling back to an IP-only key: a single IP can
    legitimately post several different accounts' or codes' attempts within
    the window, and the existing per-IP and per-account limits on these
    routes already cover that traffic.
    """
    from flask import request

    from app.hash_utils import hash_login_totp_replay_key
    from app.utils.auth_username import normalize_auth_username

    def _key() -> str:
        normalized = normalize_auth_username(request.form.get(username_field, ""))
        code = (request.form.get(code_field, "") or "").strip()
        if not normalized or not code:
            return ""
        return f"totp-once:{hash_login_totp_replay_key(normalized, code)}"

    return _key


# Use memory storage in CI/testing environments, Redis in production
# This prevents Redis connection errors in GitHub Actions
if os.environ.get('RATELIMIT_STORAGE_URI'):
    # Explicitly configured storage URI takes precedence
    storage_uri = os.environ.get('RATELIMIT_STORAGE_URI')
elif os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
    # Use memory storage in CI environments
    storage_uri = 'memory://'
elif os.environ.get('REDIS_URL'):
    # Use Redis URL if provided
    storage_uri = os.environ.get('REDIS_URL')
else:
    # Default to local Redis in production/development
    storage_uri = 'redis://localhost:6379'

limiter = Limiter(
    key_func=get_real_ip_for_limiter,
    default_limits=["500 per day", "200 per hour"],
    storage_uri=storage_uri,
    strategy="fixed-window"
)
