"""Allow grant-only Store products to omit purchase pricing.

SPEC-STORE-001 §IV.A (v1.3) requires ``price`` when ``direct_purchase_allowed``
is true and requires it to be null for a grant-only product.

Downgrade cannot restore NOT NULL while a grant-only product exists, and it has
no lawful value to invent: a backfilled price would turn a grant-only product
into a purchasable one the moment the previous revision drops
``direct_purchase_allowed``. It therefore refuses, naming the precondition,
rather than failing inside ALTER TABLE.

Revision ID: d9e0f1a2b3c4
Revises: c7d8e9f0a1b3
"""
from alembic import op
import sqlalchemy as sa


revision = 'd9e0f1a2b3c4'
down_revision = 'c7d8e9f0a1b3'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade():
    if not table_exists('store_products'):
        print("⚠️  Table 'store_products' does not exist, skipping...")
        return
    op.alter_column('store_products', 'price', nullable=True)


def downgrade():
    if not table_exists('store_products'):
        print("⚠️  Table 'store_products' does not exist, skipping...")
        return
    grant_only = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM store_products WHERE price IS NULL")
    ).scalar()
    if grant_only:
        raise RuntimeError(
            f"Cannot downgrade d9e0f1a2b3c4: {grant_only} store product version(s) "
            "have no price because they are grant-only. Retire those products or "
            "give them a price before downgrading."
        )
    op.alter_column('store_products', 'price', nullable=False)
