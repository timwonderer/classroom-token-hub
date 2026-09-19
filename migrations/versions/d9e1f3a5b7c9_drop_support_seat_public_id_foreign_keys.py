"""Drop Support's foreign keys to seats.public_id.

INV-ARC-021 §V.7 permits cross-domain foreign keys only to class_id, seat_id and
user_id. issues.actor_public_id and actor_request_trace.actor_public_id now hold
the seat's public ID only; seat deletion deletes those rows in code (DOM-SUP-001
§X). Traces still cascade with their class through the permitted class_id key.

Revision ID: d9e1f3a5b7c9
Revises: b3c4d5e6f7a8
Create Date: 2026-09-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd9e1f3a5b7c9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None

_SEAT_REFERENCES = (
    ('issues', 'fk_issues_actor_public_id_seats'),
    ('actor_request_trace', 'fk_actor_request_trace_seat'),
)


def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    """Get FKs for a column (for drops without hardcoded names)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []


def upgrade():
    for table, _name in _SEAT_REFERENCES:
        if not table_exists(table):
            continue
        for fk in get_foreign_keys_by_column(table, 'actor_public_id'):
            if fk['referred_table'] == 'seats':
                op.drop_constraint(fk['name'], table, type_='foreignkey')
                print(f"❌ Dropped {fk['name']} ({table} -> seats)")


def downgrade():
    """No-op by design.

    Neither e3c3d4e5f6a7 nor a5e5f6a7b8c9 creates a foreign key from
    actor_public_id to seats.public_id any more, so the state this revision
    downgrades to has none, and restoring one here would produce a schema no
    upgrade path ever builds. It would also be unsafe: an unclaimed seat may
    hold an earlier claimant's tickets, so these columns can legitimately
    reference a seat that is gone, which is exactly why INV-ARC-021 V.7 allows
    no such key.

    The upgrade above stays a defensive drop for databases that applied the
    earlier forms of those revisions.
    """
    return
