"""Per-role expiry for the authenticated session cookie.

Flask's ``PERMANENT_SESSION_LIFETIME`` is a single application-wide value, but
this application has three different authoritative session lifetimes, none of
which are introduced here:

  * student  -- a hard cap from login, stored on ``User.current_session_expires_at``
                and enforced by ``login_required``.
  * teacher  -- ``SESSION_TIMEOUT_MINUTES`` idle, enforced by ``admin_required``.
  * sysadmin -- ``SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES`` idle, enforced by
                ``system_admin_required``.

The cookie carrying those sessions used to outlive all three. Nothing sets
``PERMANENT_SESSION_LIFETIME``, so it is Flask's 31-day default, and the
server-side checks in ``app/auth.py`` only fire when a request arrives. A closed
tab therefore left the cookie -- including the decrypted display names cached in
it under ``display_metadata`` -- resident on the device for a month after a
ten-minute session had ended.

``SessionInterface.get_expiration_time`` receives the session object, so the
cookie's own expiry can be derived per role without mutating any
application-wide value.

SCOPE -- read before shortening anything here. This bounds *authenticated*
sessions only. A session with no recognized role deliberately falls through to
``PERMANENT_SESSION_LIFETIME``, because a pre-login session holds a CSRF token
and flash messages and nothing else: the two session keys that carry personal
data, ``display_metadata`` and ``teacher_display_name_cache``, are both written
only after a canonical authenticated context exists. The generic
permanent-session default is consequently *not* a PII-retention control, and the
31-day value must not be "hardened" on the theory that it is one. Doing so would
shorten the pre-login window that keeps a login form's CSRF token valid, in
exchange for protecting data that window never holds.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask.sessions import SecureCookieSessionInterface

from app.auth import SESSION_TIMEOUT_MINUTES, SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES

# Absolute expiry stamped into the session by a login flow that already owns an
# authoritative expiry instant. Students have one (`User.current_session_expires_at`);
# teachers and sysadmins do not, because their rules are idle-based rather than
# a fixed cap, and so they fall to the role table below.
SESSION_EXPIRES_AT_KEY = "session_expires_at"

# Keyed by the value written to `session["role"]` by the `establish_*_session`
# helpers in app/auth.py -- note the teacher role is spelled "admin" there.
_ROLE_LIFETIME_MINUTES = {
    "student": SESSION_TIMEOUT_MINUTES,
    "admin": SESSION_TIMEOUT_MINUTES,
    "sysadmin": SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES,
}


def _stamped_expiry(session) -> datetime | None:
    """Return the session's absolute expiry, or None if absent/unusable.

    A malformed stamp is treated as absent rather than fatal: the session cookie
    is an external boundary that outlives deploys, and refusing to serve a
    response because an old cookie carries an unparseable timestamp would turn a
    cosmetic problem into an outage. Falling through to the role table can only
    shorten or preserve the cookie's life, never extend it past the server-side
    check in app/auth.py, which remains the authority.
    """
    raw = session.get(SESSION_EXPIRES_AT_KEY)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class RoleScopedSessionInterface(SecureCookieSessionInterface):
    """Bound the session cookie to the authoritative lifetime of its role."""

    def get_expiration_time(self, app, session):
        if not session.permanent:
            return None

        # An explicit absolute expiry wins: it mirrors a server-side record, so
        # honoring it keeps the cookie and that record dying together. It is
        # deliberately not refreshed per request -- the rule it mirrors is a hard
        # cap from login, not an idle timeout.
        stamped = _stamped_expiry(session)
        if stamped is not None:
            return stamped

        minutes = _ROLE_LIFETIME_MINUTES.get(session.get("role"))
        if minutes is None:
            return super().get_expiration_time(app, session)

        # Idle-based roles slide forward on each request, which is what
        # SESSION_REFRESH_EACH_REQUEST already does for the server-side check.
        return datetime.now(timezone.utc) + timedelta(minutes=minutes)
