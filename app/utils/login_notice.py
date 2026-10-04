"""
Operator notice shown on the student and teacher login pages.

The notice is a small JSON file written onto the production host by the
``Login page notice`` GitHub Action (``.github/workflows/login-notice.yml``),
so posting or clearing it needs no deploy, no restart and no database write:

    {"message": "...", "expires_at": "2026-10-10T05:00:00Z", "posted_at": "..."}

It lives in Flask's instance folder by default (``instance/`` is gitignored and
untouched by the release workflow's ``git reset --hard`` / ``git clean -fd docs/``),
or at ``LOGIN_NOTICE_PATH`` when that is set.

The file is read only when a login page renders. Anything wrong with it
(missing, unreadable, malformed, expired) means "no notice": a bad notice must
never break sign-in.
"""

import json
import os
from datetime import datetime, timezone

from flask import current_app

LOGIN_NOTICE_FILENAME = "login_notice.json"
MAX_MESSAGE_LENGTH = 1000


def login_notice_path():
    configured = current_app.config.get("LOGIN_NOTICE_PATH")
    if configured:
        return configured
    return os.path.join(current_app.instance_path, LOGIN_NOTICE_FILENAME)


def parse_login_notice(raw, now=None):
    """Return the notice message from raw JSON text, or None if it should not show.

    ``expires_at`` must be an ISO 8601 timestamp carrying a UTC offset; a naive
    timestamp is refused rather than guessed at.
    """
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        return None

    expires_raw = data.get("expires_at")
    if not isinstance(expires_raw, str):
        return None
    try:
        expires_at = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if expires_at.tzinfo is None:
        return None

    now = now or datetime.now(timezone.utc)
    if now >= expires_at:
        return None
    message = message.strip()[:MAX_MESSAGE_LENGTH]
    try:
        # JSON can carry lone surrogates ("\ud800"), which would fail when
        # the page is encoded.
        message.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return message


def get_login_notice():
    """Return the active login notice message, or None."""
    path = login_notice_path()
    try:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read(16 * 1024)
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError):
        current_app.logger.warning("Login notice file could not be read", exc_info=True)
        return None
    return parse_login_notice(raw)
