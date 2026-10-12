"""Teacher display-name resolution for the admin layout, outside class context.

Audit S10: ``set_admin_display_name_cache`` / ``get_admin_display_name_cache``
used to write and read the teacher's decrypted display name through the Flask
session -- a signed but unencrypted cookie, which put plaintext PII at rest in
conflict with INV-CORE-000 section 2 and INV-ARC-018 section VII.1. Tim's
ruling (2026-10-12): resolve it fresh from the database on every call instead
of weakening that invariant for the sake of avoiding one decrypt per request.

``get_admin_display_name_cache`` now resolves directly and purges any
plaintext name a pre-fix session cookie may still be carrying.
``set_admin_display_name_cache`` is a no-op: callers (login, class-switch,
onboarding) still call it, but there is nothing left to write.

``get_teacher_display_name_cache`` / ``upsert_teacher_display_name_cache`` are
unrelated and unaffected: they cache only the literal placeholder string
"Teacher" keyed by teacher user id, never a decrypted name.
"""

from __future__ import annotations

from flask import session


ADMIN_DISPLAY_NAME_KEY = "admin_display_name"
ADMIN_DISPLAY_NAME_ID_KEY = "admin_display_name_user_id"
TEACHER_DISPLAY_NAME_CACHE_KEY = "teacher_display_name_cache"


def _purge_legacy_admin_display_name_cache() -> None:
    session.pop(ADMIN_DISPLAY_NAME_ID_KEY, None)
    session.pop(ADMIN_DISPLAY_NAME_KEY, None)


def set_admin_display_name_cache(*, user_id: int, display_name: str) -> None:
    """No-op (audit S10) -- kept so existing call sites need no change."""
    return


def get_admin_display_name_cache(*, user_id: int) -> str | None:
    """Resolve the teacher's display name directly from the database."""
    _purge_legacy_admin_display_name_cache()

    from app import db
    from app.models import Seat, User

    user = db.session.get(User, user_id)
    if user is None:
        return None
    if user.last_active_seat_id:
        seat = db.session.get(Seat, user.last_active_seat_id)
        if seat and seat.identity_profile:
            return seat.identity_profile.full_name
    return user.get_display_username()


def clear_admin_display_name_cache() -> None:
    _purge_legacy_admin_display_name_cache()


def get_teacher_display_name_cache() -> dict[str, str]:
    cache = session.get(TEACHER_DISPLAY_NAME_CACHE_KEY)
    if isinstance(cache, dict):
        return cache
    return {}


def upsert_teacher_display_name_cache(entries: dict[str, str]) -> None:
    cache = get_teacher_display_name_cache()
    cache.update(entries)
    session[TEACHER_DISPLAY_NAME_CACHE_KEY] = cache


def clear_teacher_display_name_cache() -> None:
    session.pop(TEACHER_DISPLAY_NAME_CACHE_KEY, None)
