"""Rename the Store overdue-purchase flag to its SPEC-STORE-001 name.

SPEC-STORE-001 §IV.C and §IV.D name the product field that permits a purchase
while an obligation is overdue ``available_with_overdue_obligations``. Migration
e0f1a2b3c4d5 introduced it as ``essential_when_overdue``, so the schema carried
a field the governing payload schema does not declare (§III.A). This renames
the column in place; values are preserved.

Revision ID: b4c5d6e7f8a9
Revises: 046dccd4451e
"""
from alembic import op
import sqlalchemy as sa

revision = 'b4c5d6e7f8a9'
down_revision = '046dccd4451e'
branch_labels = None
depends_on = None


_TABLE = 'store_products'
_OLD = 'essential_when_overdue'
_NEW = 'available_with_overdue_obligations'


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


def upgrade():
    if not table_exists(_TABLE):
        print(f"⚠️  Table '{_TABLE}' does not exist, skipping...")
        return
    if column_exists(_TABLE, _OLD) and not column_exists(_TABLE, _NEW):
        op.alter_column(_TABLE, _OLD, new_column_name=_NEW)
        print(f"✅ Renamed {_TABLE}.{_OLD} to {_NEW}")
    else:
        print(f"⚠️  {_TABLE}.{_OLD} is absent or {_NEW} already exists, skipping...")


def downgrade():
    if not table_exists(_TABLE):
        print(f"⚠️  Table '{_TABLE}' does not exist, skipping...")
        return
    if column_exists(_TABLE, _NEW) and not column_exists(_TABLE, _OLD):
        op.alter_column(_TABLE, _NEW, new_column_name=_OLD)
        print(f"❌ Renamed {_TABLE}.{_NEW} back to {_OLD}")
    else:
        print(f"⚠️  {_TABLE}.{_NEW} is absent or {_OLD} already exists, skipping...")
