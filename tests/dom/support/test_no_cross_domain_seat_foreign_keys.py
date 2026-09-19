"""No migration may constrain `actor_public_id` against `seats.public_id`.

INV-ARC-021 §V.7 permits cross-domain foreign keys only to `class_id`,
`seat_id` and `user_id`. `actor_public_id` is none of those, and DOM-SUP-001 §X
makes the lifetime rule explicit: a support ticket or request trace is swept
when its seat is deleted, by the explicit sweep in
`app/utils/student_deletion.py`, not by a database cascade.

The chain used to create these keys and then drop them a few revisions later,
which was both self-contradictory and unsafe: nothing reconciled `issues`
first, so one legacy ticket whose `actor_public_id` no longer matched a live
seat — an unclaimed seat holding an earlier claimant's tickets, for instance —
failed the upgrade before it could reach the revision that removes the key.

This guards the whole corpus rather than the three revisions involved, because
the next one would be written the same way.
"""

from __future__ import annotations

import pathlib
import re

MIGRATIONS = pathlib.Path(__file__).resolve().parents[3] / "migrations" / "versions"

# The revision whose entire purpose is removing these keys still names them.
_REMOVAL_REVISION = "d9e1f3a5b7c9"

_CREATE_FK = re.compile(
    r"create_foreign_key\([^)]*actor_public_id[^)]*\)", re.DOTALL
)


def test_no_migration_creates_a_foreign_key_on_actor_public_id():
    offenders = []
    for path in sorted(MIGRATIONS.glob("*.py")):
        if path.name.startswith(_REMOVAL_REVISION):
            continue
        text = path.read_text(encoding="utf-8")
        for match in _CREATE_FK.finditer(text):
            if "seats" in match.group(0):
                offenders.append(f"{path.name}: {' '.join(match.group(0).split())[:120]}")
    assert offenders == [], (
        "actor_public_id carries no foreign key to seats (INV-ARC-021 §V.7); "
        f"seat-scoped sweeps handle deletion instead: {offenders}"
    )


def test_the_removal_revision_does_not_restore_the_key_on_downgrade():
    """Downgrade must not build a schema no upgrade path produces."""
    path = next(MIGRATIONS.glob(f"{_REMOVAL_REVISION}*.py"))
    downgrade = path.read_text(encoding="utf-8").split("def downgrade()", 1)[1]
    assert "create_foreign_key" not in downgrade
