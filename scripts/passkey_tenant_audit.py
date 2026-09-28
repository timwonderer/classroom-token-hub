"""List passwordless.dev users that name no current principal, and optionally delete them.

passwordless.dev keeps its own users, credentials and aliases. Before
2026-09-28 nothing removed them when an account went away, and the
2026-09-26 launch wipe left pre-launch registrations behind. Such an entry
holds its alias, so that username can never register a passkey again (HTTP
409 ``alias_conflict``).

An entry is an orphan when its user id is not ``user_<UUID>`` for a ``users``
row that exists. Since 2026-09-28 sign-in also requires a locally recorded
credential, so an orphan cannot sign anyone in; it only blocks aliases.

Read-only by default:

    FLASK_APP=wsgi.py python scripts/passkey_tenant_audit.py

Deleting requires ``--delete`` and typing the number of orphans to confirm:

    FLASK_APP=wsgi.py python scripts/passkey_tenant_audit.py --delete

Deletion is ``/users/delete``, which removes the entry's credentials and aliases.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def find_orphans(summaries, existing_user_ids):
    """The tenant entries whose user id names no existing principal."""
    from app.utils.user_ids import parse_passkey_external_id
    return [
        s for s in summaries
        if parse_passkey_external_id(s.user_id) not in existing_user_ids
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--delete", action="store_true", help="delete the orphans after confirmation")
    args = parser.parse_args(argv)

    from app import app
    from app.extensions import db
    from app.models import User
    from app.utils.passwordless_client import get_passwordless_client

    with app.app_context():
        client = get_passwordless_client()
        summaries = client.get_users()
        existing = {str(uid) for (uid,) in db.session.query(User.id).all()}
        orphans = find_orphans(summaries, existing)

        print(f"passwordless.dev users: {len(summaries)}; naming no current principal: {len(orphans)}")
        for s in orphans:
            print(f"  {s.user_id}  credentials={s.credentials_count}  aliases={s.alias_count}  last_used={s.last_used_at}")

        if not args.delete or not orphans:
            return 0
        answer = input(f"Type {len(orphans)} to delete these {len(orphans)} passwordless.dev users: ")
        if answer.strip() != str(len(orphans)):
            print("Not confirmed; nothing deleted.")
            return 1

        from passwordless import DeleteUser
        for s in orphans:
            client.delete_user(DeleteUser(user_id=s.user_id))
            print(f"  deleted {s.user_id}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
