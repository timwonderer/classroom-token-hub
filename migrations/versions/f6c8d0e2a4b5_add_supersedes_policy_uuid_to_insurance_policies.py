"""Add supersedes_policy_uuid to insurance_policies (DOM-POL-001A §D)

The version a row replaces when a teacher edits a policy or puts a hidden one back
on sale (owner ruling 2026-10-14). Set at creation and never changed; NULL means the
row replaces nothing. Insurance renewal follows it so an existing holder continues
under the successor through a new entitlement at the coverage boundary
(DOM-STORE-001 §VIII.E.1, FEAT-STOR-007 §V.A).

No backfill: production held no retired or hidden insurance versions when this was
written (checked 2026-10-14), so no existing row has a successor to record.

Revision ID: f6c8d0e2a4b5
Revises: e5b7c9d1f3a4
Create Date: 2026-10-14
"""
from alembic import op
import sqlalchemy as sa


revision = 'f6c8d0e2a4b5'
down_revision = 'e5b7c9d1f3a4'
branch_labels = None
depends_on = None


TABLE = 'insurance_policies'
COLUMN = 'supersedes_policy_uuid'
INDEX = 'ix_insurance_policies_supersedes_policy_uuid'


def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def upgrade():
    if not table_exists(TABLE):
        print(f"⚠️  Table '{TABLE}' does not exist, skipping...")
        return
    if not column_exists(TABLE, COLUMN):
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(length=36), nullable=True))
        print(f"✅ Added {COLUMN} to {TABLE}")
    else:
        print(f"⚠️  Column '{COLUMN}' already exists on '{TABLE}', skipping...")
    if not index_exists(TABLE, INDEX):
        op.create_index(INDEX, TABLE, [COLUMN], unique=False)
        print(f"✅ Created index {INDEX}")
    else:
        print(f"⚠️  Index '{INDEX}' already exists, skipping...")


def downgrade():
    if not table_exists(TABLE):
        return
    if index_exists(TABLE, INDEX):
        op.drop_index(INDEX, table_name=TABLE)
        print(f"❌ Dropped index {INDEX}")
    if column_exists(TABLE, COLUMN):
        op.drop_column(TABLE, COLUMN)
        print(f"❌ Dropped {COLUMN} from {TABLE}")
    else:
        print(f"⚠️  Column '{COLUMN}' does not exist on '{TABLE}', skipping...")
