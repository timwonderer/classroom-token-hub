"""Bind support snapshot lifetime to its originating seat (DOM-SUP-001 X).

Validate existing references; never infer identity or silently delete old tickets.

This revision originally created `fk_issues_actor_public_id_seats`, a foreign key
from `issues.actor_public_id` to `seats.public_id`. It no longer does, for two
reasons, both established later in this same chain:

* INV-ARC-021 V.7 permits cross-domain foreign keys only to `class_id`,
  `seat_id` and `user_id`. `d9e1f3a5b7c9` drops this key for that reason, so
  creating it here only to remove it a few revisions later contradicted the
  contract the chain is moving toward.
* Creating it was not safe on a populated database. Unlike the request-trace
  revision, which deletes orphaned rows before constraining the column, nothing
  here reconciled `issues` first. A single legacy ticket whose `actor_public_id`
  no longer matches a live seat — an unclaimed seat that kept an earlier
  claimant's tickets, for instance — failed this revision and stopped the
  upgrade before it could reach `d9e1f3a5b7c9`.

Seat deletion now removes a seat's tickets explicitly rather than by cascade
(`app/utils/student_deletion.py`), which is what DOM-SUP-001 X requires of a
column carrying no foreign key. `d9e1f3a5b7c9` still drops the key defensively,
so a database that applied an earlier form of this revision converges here.
"""
from alembic import op
import sqlalchemy as sa

revision = 'e3c3d4e5f6a7'
down_revision = 'd2b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('issues'):
        return
    with op.batch_alter_table('issues') as batch:
        batch.alter_column('class_public_id', existing_type=sa.String(36), nullable=False)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('issues'):
        with op.batch_alter_table('issues') as batch:
            batch.alter_column('class_public_id', existing_type=sa.String(36), nullable=True)
