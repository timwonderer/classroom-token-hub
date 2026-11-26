"""Replace the Store pricing tier with the required economic role.

SPEC-ECON-003 §4.7 retires the four-tier Store price ladder in favour of three
economic roles. SPEC-STORE-001 §IV.A makes ``economic_role`` a required field,
so it cannot be introduced as a nullable column without becoming exactly the
compatibility bridge the append-only product model forbids: the backfill runs
inside this migration and the column lands NOT NULL.

The reverse mapping is lossy by construction — ``basic`` and ``standard`` both
collapse into ``necessity`` — so downgrade restores the column and the coarse
tier, not the original value.

Revision ID: 046dccd4451e
Revises: f3a4b5c6d7e8
"""
from alembic import op
import sqlalchemy as sa

revision = '046dccd4451e'
down_revision = 'f3a4b5c6d7e8'
branch_labels = None
depends_on = None


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


def constraint_exists(table_name, constraint_name):
    """Check if a named check constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        names = [c['name'] for c in inspector.get_check_constraints(table_name)]
        return constraint_name in names
    except Exception:
        return False


def upgrade():
    if not table_exists('store_products'):
        print("⚠️  Table 'store_products' does not exist, skipping...")
        return

    if not column_exists('store_products', 'economic_role'):
        op.add_column(
            'store_products',
            sa.Column('economic_role', sa.String(length=20), nullable=True),
        )
        print("✅ Added economic_role column to store_products")
    else:
        print("⚠️  Column 'economic_role' already exists, skipping add...")

    # Deterministic backfill. A collective goal is never tiered (Store pricing
    # tiers were forbidden for it), and it is a shared optional purchase rather
    # than a class necessity, so it resolves to add_on instead of the default.
    if column_exists('store_products', 'tier'):
        op.execute("""
            UPDATE store_products
            SET economic_role = CASE
                WHEN tier IN ('basic', 'standard') THEN 'necessity'
                WHEN tier = 'premium' THEN 'convenience'
                WHEN tier = 'luxury' THEN 'add_on'
                WHEN item_type = 'collective' THEN 'add_on'
                ELSE 'necessity'
            END
            WHERE economic_role IS NULL
        """)
    else:
        op.execute("""
            UPDATE store_products
            SET economic_role = CASE
                WHEN item_type = 'collective' THEN 'add_on'
                ELSE 'necessity'
            END
            WHERE economic_role IS NULL
        """)
    print("✅ Backfilled economic_role from the retired pricing tier")

    op.alter_column(
        'store_products', 'economic_role',
        existing_type=sa.String(length=20), nullable=False,
    )

    if not constraint_exists('store_products', 'ck_store_products_economic_role'):
        op.create_check_constraint(
            'ck_store_products_economic_role',
            'store_products',
            "economic_role IN ('necessity','convenience','add_on')",
        )
        print("✅ Added economic_role check constraint")

    if column_exists('store_products', 'tier'):
        op.drop_column('store_products', 'tier')
        print("❌ Dropped retired tier column from store_products")
    else:
        print("⚠️  Column 'tier' does not exist, skipping drop...")


def downgrade():
    if not table_exists('store_products'):
        print("⚠️  Table 'store_products' does not exist, skipping...")
        return

    if not column_exists('store_products', 'tier'):
        op.add_column(
            'store_products',
            sa.Column('tier', sa.String(length=20), nullable=True),
        )
        print("✅ Restored tier column on store_products")

    # Lossy by construction: necessity covered both basic and standard.
    if column_exists('store_products', 'economic_role'):
        op.execute("""
            UPDATE store_products
            SET tier = CASE
                WHEN economic_role = 'necessity' THEN 'standard'
                WHEN economic_role = 'convenience' THEN 'premium'
                WHEN economic_role = 'add_on' THEN 'luxury'
            END
            WHERE tier IS NULL AND item_type <> 'collective'
        """)

    if constraint_exists('store_products', 'ck_store_products_economic_role'):
        op.drop_constraint(
            'ck_store_products_economic_role', 'store_products', type_='check'
        )

    if column_exists('store_products', 'economic_role'):
        op.drop_column('store_products', 'economic_role')
        print("❌ Dropped economic_role column from store_products")
