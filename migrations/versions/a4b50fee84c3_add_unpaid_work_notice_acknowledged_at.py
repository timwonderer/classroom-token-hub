"""Record when a class's teacher dismissed the unpaid-work notice

Owner rulings 2026-10-01 (DOM-CLASS-001 §VII.1, DOM-PROD-001 §XV.6,
FEAT-CLASS-008). A class can record Start Work before it has any payroll
setting; its teacher is told once, and may dismiss the notice. The dismissal is
one nullable timestamp on the class row:

- NULL means the teacher has not dismissed it;
- it is written once by FEAT-CLASS-008 with ``... WHERE ... IS NULL``, so a
  second dismissal keeps the first timestamp;
- who dismissed is the class's single teacher seat, derivable, so not stored;
- it lives and dies with the class row (INV-ARC-013), so there is no foreign
  key, trigger or teardown step to add.

``classes`` has no UPDATE trigger, so nothing refuses the write.

Data mapping: none. Every existing class starts as not dismissed. A class that
already has a payroll setting never shows the notice, whatever this column holds.

Deploy: adding a nullable column with no default is a catalog-only change, but
it still takes a brief ACCESS EXCLUSIVE lock on ``classes``, which every request
reads. Production's role carries lock_timeout=10s, so run this upgrade with
PGOPTIONS='-c lock_timeout=0'.

Revision ID: a4b50fee84c3
Revises: 624c6b7223df
Create Date: 2026-10-01 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4b50fee84c3'
down_revision = '624c6b7223df'
branch_labels = None
depends_on = None


TABLE = 'classes'
COLUMN = 'unpaid_work_notice_acknowledged_at'


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

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
    """Check if a foreign key constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    """Get foreign key constraints that reference a specific column."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []


# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def upgrade():
    if not table_exists(TABLE):
        print(f"⚠️  Table '{TABLE}' does not exist, skipping...")
        return
    if not column_exists(TABLE, COLUMN):
        op.add_column(TABLE, sa.Column(COLUMN, sa.DateTime(timezone=True), nullable=True))
        print(f"✅ Added {COLUMN} to {TABLE}")
    else:
        print(f"⚠️  Column '{COLUMN}' already exists on '{TABLE}', skipping...")


def downgrade():
    if column_exists(TABLE, COLUMN):
        op.drop_column(TABLE, COLUMN)
        print(f"❌ Dropped {COLUMN} from {TABLE}")
    else:
        print(f"⚠️  Column '{COLUMN}' does not exist on '{TABLE}', skipping...")
