"""The one place a ``users.id`` is parsed from outside the database.

``users.id`` is a random UUID (INV-ARC-019 §VI). Code that reads it from a
``User`` row passes it along untouched. Values that arrive as text (the session
cookie, the passwordless.dev external user id) are parsed here, so a malformed
or pre-UUID value is refused before it reaches a query, where Postgres would
reject it as invalid ``uuid`` input.
"""

from __future__ import annotations

import uuid

# passwordless.dev identifies our principals as "user_<users.id>" (DOM-IDEN-003).
PASSKEY_EXTERNAL_ID_PREFIX = "user_"


def parse_user_id(value) -> str | None:
    """Return ``value`` as a canonical ``users.id`` string, or None if it is not one.

    Integers are refused: an integer is a pre-UUID id, and it names no one now.
    """
    if not isinstance(value, (str, uuid.UUID)):
        return None
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        return None


def session_user_id(session) -> str | None:
    """The authenticated principal named by the session, if it names one validly."""
    return parse_user_id(session.get("user_id"))


def passkey_external_id(user_id) -> str:
    """The passwordless.dev user id for a principal."""
    return f"{PASSKEY_EXTERNAL_ID_PREFIX}{user_id}"


def parse_passkey_external_id(external_id) -> str | None:
    """The ``users.id`` inside a passwordless.dev user id, or None.

    Pre-UUID external ids ("user_3") parse to None. They were issued before the
    2026-09-26 reset and name nobody who exists now.
    """
    if not isinstance(external_id, str) or not external_id.startswith(PASSKEY_EXTERNAL_ID_PREFIX):
        return None
    return parse_user_id(external_id[len(PASSKEY_EXTERNAL_ID_PREFIX):])
