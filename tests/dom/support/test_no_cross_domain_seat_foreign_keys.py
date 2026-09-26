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


def _forbidden_keys(source: str) -> list[str]:
    """Foreign keys this source creates from actor_public_id to seats.

    Pure over the text so the guard itself can be tested against a known
    violation, rather than only ever being run over a corpus that passes.
    """
    return [
        " ".join(match.group(0).split())[:120]
        for match in _CREATE_FK.finditer(source)
        if "seats" in match.group(0)
    ]


def test_no_migration_creates_a_foreign_key_on_actor_public_id():
    offenders = []
    for path in sorted(MIGRATIONS.glob("*.py")):
        if path.name.startswith(_REMOVAL_REVISION):
            continue
        for found in _forbidden_keys(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.name}: {found}")
    assert offenders == [], (
        "actor_public_id carries no foreign key to seats (INV-ARC-021 §V.7); "
        f"seat-scoped sweeps handle deletion instead: {offenders}"
    )


def test_the_guard_catches_a_migration_that_adds_the_key():
    """The mutation proof: commit the forbidden thing, confirm CI stops it.

    Without this, a green check above means either "no migration creates the
    key" or "the pattern stopped matching" — and the two are indistinguishable
    from the outside. Each spelling below is one a real migration would plausibly
    use, including the batch form, which is how both removed instances were
    written.
    """
    violations = [
        """op.create_foreign_key('fk_issues_actor_public_id_seats', 'issues', 'seats',
                                 ['actor_public_id'], ['public_id'], ondelete='CASCADE')""",
        """with op.batch_alter_table('issues') as batch:
               batch.create_foreign_key(_NAME, 'seats', ['actor_public_id'], ['public_id'])""",
        """op.create_foreign_key(
               name,
               'actor_request_trace',
               'seats',
               ['actor_public_id'],
               ['public_id'],
           )""",
    ]
    for source in violations:
        assert _forbidden_keys(source), f"guard missed a forbidden key:\n{source}"

    # And it must not fire on the permitted key to classes, or the guard would
    # block the class_id cascade the chain legitimately relies on.
    permitted = """op.create_foreign_key('fk_actor_request_trace_class_id_classes',
                        'actor_request_trace', 'classes', ['class_id'], ['class_id'],
                        ondelete='CASCADE')"""
    assert not _forbidden_keys(permitted)


def test_the_removal_revision_does_not_restore_the_key_on_downgrade():
    """Downgrade must not build a schema no upgrade path produces."""
    path = next(MIGRATIONS.glob(f"{_REMOVAL_REVISION}*.py"))
    downgrade = path.read_text(encoding="utf-8").split("def downgrade()", 1)[1]
    assert "create_foreign_key" not in downgrade
