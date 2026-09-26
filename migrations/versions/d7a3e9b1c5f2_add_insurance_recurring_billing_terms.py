"""Add recurring billing terms to insurance_policies (DOM-POL-001A §V.E)

An insurance definition now fixes, at authoring, the terms its recurring premium
lineage runs on (FEAT-STOR-007):

- ``bill_preview_days``  — how many class-local days before a coverage boundary the
  next period's premium is assessed (``0 < preview < minimum_period_duration``);
- ``nonpayment_mode``    — ``ACCUMULATE`` or ``CANCEL_AFTER_X_DAYS``;
- ``cancel_after_days``  — the nonpayment deadline, required iff
  ``CANCEL_AFTER_X_DAYS``.

The columns are nullable in the database. The production database is wiped at
launch, so no backfill is needed; FEAT-CLASS-003 authoring validation requires
them on every new definition, and the insurance purchase fails closed on a
definition that lacks lawful recurring terms.

Revision ID: d7a3e9b1c5f2
Revises: c4d6e8f0a2b3
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa


revision = 'd7a3e9b1c5f2'
down_revision = 'c4d6e8f0a2b3'
branch_labels = None
depends_on = None


TABLE = 'insurance_policies'
COLUMNS = (
    ('bill_preview_days', sa.Integer()),
    ('nonpayment_mode', sa.String(length=24)),
    ('cancel_after_days', sa.Integer()),
)


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
    for name, column_type in COLUMNS:
        if not column_exists(TABLE, name):
            op.add_column(TABLE, sa.Column(name, column_type, nullable=True))
            print(f"✅ Added {name} to {TABLE}")
        else:
            print(f"⚠️  Column '{name}' already exists on '{TABLE}', skipping...")


def downgrade():
    if not table_exists(TABLE):
        return
    for name, _column_type in reversed(COLUMNS):
        if column_exists(TABLE, name):
            op.drop_column(TABLE, name)
            print(f"❌ Dropped {name} from {TABLE}")
        else:
            print(f"⚠️  Column '{name}' does not exist on '{TABLE}', skipping...")
