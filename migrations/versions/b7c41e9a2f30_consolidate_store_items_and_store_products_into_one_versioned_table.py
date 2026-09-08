"""Consolidate store_items and store_products into one versioned product table

One product was previously described by two records: ``store_items`` (a mutable,
integer-keyed catalog row that teacher forms wrote) and ``store_products`` (a
JSON-payload policy row that purchases resolved against), joined by nothing but
``payload["product_id"]`` and kept in step by a synchronization routine. They
drifted. This collapses them into the shape every other policy family already
uses: a UUID-keyed, append-only definition row with a mutable availability
projection (DOM-POL-001 §VI.0, §IX).

Two identifiers, deliberately distinct:

* ``policy_uuid`` — the *version*. Primary key. Create and edit both mint one.
  An entitlement freezes it, so a student keeps the terms they bought under.
* ``product_lineage_uuid`` — the *product*. Stable across versions. Everything
  derived — units sold, stock remaining, collective-goal progress, per-seat
  visibility — hangs off this, because those describe the product rather than
  any one version of it.

The partial unique index ``uq_store_products_one_live_per_lineage`` is what
makes "edit = supersede" safe: it makes two simultaneously sellable versions of
one product a database error rather than a pricing bug.

This migration is **destructive by design and by authorization**. Both legacy
tables are dropped and recreated rather than converted:

* ``store_items.id`` is an integer with no lineage identity, so there is no
  honest way to reconstruct which rows were versions of the same product.
* ``store_products.payload`` is untyped JSON whose keys were never constrained,
  so a column-wise conversion would be a guess.
* ``store_items.is_rent_linked`` is dropped rather than converted. Rent linkage
  now lives on ``RentSettings.satisfaction_benefits``, and rent is versioned:
  writing links onto the *current* rent policy would retroactively alter cycles
  already underway, which is precisely the behaviour the redesign removes.

The user authorized wiping the development database for this change.

Revision ID: b7c41e9a2f30
Revises: 97e131ddb211
Create Date: 2026-09-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c41e9a2f30'
down_revision = '97e131ddb211'
branch_labels = None
depends_on = None


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


def constraint_exists(table_name, constraint_name):
    """Check if a unique constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        constraints = [c['name'] for c in inspector.get_unique_constraints(table_name)]
        return constraint_name in constraints
    except Exception:
        return False


def get_unique_constraints_by_column(table_name, column_name):
    """Get unique constraints covering a column, without hardcoding names.

    A UniqueConstraint owns its backing index, so PostgreSQL refuses
    ``DROP INDEX`` on it — it has to be dropped as a constraint, and the name
    it was created under varies with the environment.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            c for c in inspector.get_unique_constraints(table_name)
            if column_name in c['column_names']
        ]
    except Exception:
        return []


def get_foreign_keys_by_column(table_name, column_name):
    """Get FK constraints on a column, so downgrade need not hardcode names."""
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
    # ------------------------------------------------------------------
    # 1. entitlement_events.product_id  int -> String(36) lineage
    #
    # Emptied rather than cast. The old value was a ``store_items.id``, and
    # the new one names a product lineage; there is no mapping between them
    # once the catalog is dropped. An event pointing at a lineage that does
    # not exist would resolve to nothing anyway, so the honest value is NULL.
    # ------------------------------------------------------------------
    if column_exists('entitlement_events', 'product_id'):
        op.execute("UPDATE entitlement_events SET product_id = NULL")
        op.alter_column(
            'entitlement_events',
            'product_id',
            existing_type=sa.Integer(),
            type_=sa.String(length=36),
            existing_nullable=True,
            postgresql_using='product_id::text',
        )
        print("✅ entitlement_events.product_id retyped to String(36) (lineage)")

    # Now a lookup key, not just a label: teacher/class deletion and
    # entitlement resolution both filter events by lineage.
    if not index_exists('entitlement_events', 'ix_entitlement_events_product_id'):
        op.create_index(
            'ix_entitlement_events_product_id',
            'entitlement_events',
            ['product_id'],
        )

    # ------------------------------------------------------------------
    # 2. store_item_visibility  store_item_id -> product_lineage_uuid
    #
    # Visibility is a property of the *product*: a teacher who restricted an
    # item to one section expects that to hold after they edit the price.
    # Rows are cleared because their integer target is going away, and the
    # FK goes with the column — the lineage is a locator shared by many
    # rows, following the same non-FK-UUID discipline as policy_uuid.
    # ------------------------------------------------------------------
    if table_exists('store_item_visibility'):
        op.execute("DELETE FROM store_item_visibility")

        for fk in get_foreign_keys_by_column('store_item_visibility', 'store_item_id'):
            op.drop_constraint(fk['name'], 'store_item_visibility', type_='foreignkey')

        # Declared as a UniqueConstraint, so it owns its backing index and
        # must be dropped as a constraint; DROP INDEX is refused. Discovered
        # by column rather than by name, which varies across environments.
        for uq in get_unique_constraints_by_column('store_item_visibility', 'store_item_id'):
            op.drop_constraint(uq['name'], 'store_item_visibility', type_='unique')
        if index_exists('store_item_visibility', 'ix_store_item_visibility_store_item_id'):
            op.drop_index('ix_store_item_visibility_store_item_id', table_name='store_item_visibility')

        if column_exists('store_item_visibility', 'store_item_id'):
            op.drop_column('store_item_visibility', 'store_item_id')

        if not column_exists('store_item_visibility', 'product_lineage_uuid'):
            op.add_column(
                'store_item_visibility',
                sa.Column('product_lineage_uuid', sa.String(length=36), nullable=False),
            )
        if not index_exists('store_item_visibility', 'ix_store_item_visibility_product_lineage_uuid'):
            op.create_index(
                'ix_store_item_visibility_product_lineage_uuid',
                'store_item_visibility',
                ['product_lineage_uuid'],
            )
        if not constraint_exists('store_item_visibility', 'uq_store_item_visibility_lineage_seat'):
            op.create_unique_constraint(
                'uq_store_item_visibility_lineage_seat',
                'store_item_visibility',
                ['product_lineage_uuid', 'seat_id'],
            )
        print("✅ store_item_visibility rekeyed to product_lineage_uuid")

    # ------------------------------------------------------------------
    # 3. Drop both legacy product tables.
    # ------------------------------------------------------------------
    if table_exists('store_products'):
        op.drop_table('store_products')
        print("❌ Dropped legacy JSON-payload store_products")
    if table_exists('store_items'):
        op.drop_table('store_items')
        print("❌ Dropped legacy store_items catalog")

    # ------------------------------------------------------------------
    # 4. Recreate store_products in the versioned policy shape.
    # ------------------------------------------------------------------
    if not table_exists('store_products'):
        op.create_table(
            'store_products',
            # The version. Immutable once written.
            sa.Column('policy_uuid', sa.String(length=36), nullable=False),
            # The product. Shared by every version in the lineage.
            sa.Column('product_lineage_uuid', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('class_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('tier', sa.String(length=20), nullable=True),
            sa.Column('item_type', sa.String(length=20), nullable=False, server_default='delayed'),
            # Configured ceiling, not a balance. Units remaining are derived
            # from GRANTED entitlement events; DOM-STORE-001 §VII.A forbids
            # persisting the remainder.
            sa.Column('inventory_total', sa.Integer(), nullable=True),
            sa.Column('limit_per_student', sa.Integer(), nullable=True),
            sa.Column('auto_delist_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('auto_expiry_days', sa.Integer(), nullable=True),
            sa.Column('is_long_term_goal', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('bypass_cwi_warnings', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('is_bundle', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('bundle_quantity', sa.Integer(), nullable=True),
            sa.Column('bulk_discount_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('bulk_discount_quantity', sa.Integer(), nullable=True),
            sa.Column('bulk_discount_percentage', sa.Float(), nullable=True),
            sa.Column('collective_goal_type', sa.String(length=20), nullable=True),
            sa.Column('collective_goal_target', sa.Integer(), nullable=True),
            sa.Column('collective_goal_expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('collective_goal_instance_code', sa.String(length=36), nullable=True),
            sa.Column('redemption_prompt', sa.Text(), nullable=True),
            # The ONLY mutable field on an otherwise immutable row.
            sa.Column('availability_state', sa.String(length=16), nullable=False, server_default='IN_USE'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_by_seat_id', sa.Integer(), nullable=True),
            sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('policy_uuid'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['created_by_seat_id'], ['seats.id'], ondelete='SET NULL'),
            sa.CheckConstraint(
                "availability_state IN ('IN_USE','HIDDEN','RETIRED')",
                name='ck_store_products_availability_state',
            ),
        )
        print("✅ Created store_products in versioned policy shape")

    if not index_exists('store_products', 'ix_store_products_product_lineage_uuid'):
        op.create_index(
            'ix_store_products_product_lineage_uuid',
            'store_products',
            ['product_lineage_uuid'],
        )
    if not index_exists('store_products', 'ix_store_products_class_id'):
        op.create_index('ix_store_products_class_id', 'store_products', ['class_id'])
    if not index_exists('store_products', 'ix_store_products_collective_goal_instance_code'):
        op.create_index(
            'ix_store_products_collective_goal_instance_code',
            'store_products',
            ['collective_goal_instance_code'],
        )
    if not index_exists('store_products', 'ix_store_products_class_availability'):
        op.create_index(
            'ix_store_products_class_availability',
            'store_products',
            ['class_id', 'availability_state'],
        )
    if not index_exists('store_products', 'ix_store_products_class_created'):
        op.create_index(
            'ix_store_products_class_created',
            'store_products',
            ['class_id', 'created_at'],
        )
    # At most one sellable version per product. This is what makes
    # "edit = supersede" safe rather than merely intended.
    if not index_exists('store_products', 'uq_store_products_one_live_per_lineage'):
        op.create_index(
            'uq_store_products_one_live_per_lineage',
            'store_products',
            ['product_lineage_uuid'],
            unique=True,
            postgresql_where=sa.text("availability_state = 'IN_USE'"),
        )
        print("✅ One-live-version-per-lineage constraint in place")


def downgrade():
    """Restore the two-table split.

    Structure only. The product data cannot come back — a version history has
    no faithful projection onto a single mutable catalog row, and the JSON
    payloads were destroyed on the way up.
    """
    if table_exists('store_products'):
        op.drop_table('store_products')
        print("❌ Dropped versioned store_products")

    if not table_exists('store_items'):
        op.create_table(
            'store_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('class_id', sa.String(length=36), nullable=True),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('tier', sa.String(length=20), nullable=True),
            sa.Column('item_type', sa.String(length=20), nullable=False, server_default='delayed'),
            sa.Column('inventory', sa.Integer(), nullable=True),
            sa.Column('limit_per_student', sa.Integer(), nullable=True),
            sa.Column('auto_delist_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('auto_expiry_days', sa.Integer(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('is_long_term_goal', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('bypass_cwi_warnings', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('is_bundle', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('bundle_quantity', sa.Integer(), nullable=True),
            sa.Column('bulk_discount_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('bulk_discount_quantity', sa.Integer(), nullable=True),
            sa.Column('bulk_discount_percentage', sa.Float(), nullable=True),
            sa.Column('collective_goal_type', sa.String(length=20), nullable=True),
            sa.Column('collective_goal_target', sa.Integer(), nullable=True),
            sa.Column('collective_goal_expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('collective_goal_instance_code', sa.String(length=36), nullable=True),
            sa.Column('redemption_prompt', sa.Text(), nullable=True),
            sa.Column('is_rent_linked', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id']),
        )
        if not index_exists('store_items', 'ix_store_items_class_id'):
            op.create_index('ix_store_items_class_id', 'store_items', ['class_id'])
        if not index_exists('store_items', 'ix_store_items_collective_goal_instance_code'):
            op.create_index(
                'ix_store_items_collective_goal_instance_code',
                'store_items',
                ['collective_goal_instance_code'],
            )
        print("✅ Restored legacy store_items (structure only)")

    if not table_exists('store_products'):
        op.create_table(
            'store_products',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('policy_uuid', sa.String(length=36), nullable=False),
            sa.Column('class_id', sa.String(length=36), nullable=False),
            sa.Column('payload', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_by_seat_id', sa.Integer(), nullable=True),
            sa.Column('is_retired', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id']),
            sa.ForeignKeyConstraint(['created_by_seat_id'], ['seats.id']),
        )
        if not index_exists('store_products', 'ix_store_products_policy_uuid'):
            op.create_index('ix_store_products_policy_uuid', 'store_products', ['policy_uuid'], unique=True)
        if not index_exists('store_products', 'ix_store_products_class_id'):
            op.create_index('ix_store_products_class_id', 'store_products', ['class_id'])
        if not index_exists('store_products', 'ix_store_products_class_retired'):
            op.create_index('ix_store_products_class_retired', 'store_products', ['class_id', 'is_retired'])
        if not index_exists('store_products', 'ix_store_products_class_created'):
            op.create_index('ix_store_products_class_created', 'store_products', ['class_id', 'created_at'])
        print("✅ Restored legacy JSON-payload store_products (structure only)")

    # store_item_visibility back to the integer catalog key.
    if table_exists('store_item_visibility'):
        op.execute("DELETE FROM store_item_visibility")
        for uq in get_unique_constraints_by_column('store_item_visibility', 'product_lineage_uuid'):
            op.drop_constraint(uq['name'], 'store_item_visibility', type_='unique')
        if index_exists('store_item_visibility', 'ix_store_item_visibility_product_lineage_uuid'):
            op.drop_index(
                'ix_store_item_visibility_product_lineage_uuid',
                table_name='store_item_visibility',
            )
        if column_exists('store_item_visibility', 'product_lineage_uuid'):
            op.drop_column('store_item_visibility', 'product_lineage_uuid')
        if not column_exists('store_item_visibility', 'store_item_id'):
            op.add_column(
                'store_item_visibility',
                sa.Column('store_item_id', sa.Integer(), nullable=False),
            )
            op.create_foreign_key(
                'store_item_visibility_store_item_id_fkey',
                'store_item_visibility',
                'store_items',
                ['store_item_id'],
                ['id'],
                ondelete='CASCADE',
            )
        if not index_exists('store_item_visibility', 'ix_store_item_visibility_store_item_id'):
            op.create_index(
                'ix_store_item_visibility_store_item_id',
                'store_item_visibility',
                ['store_item_id'],
            )
        if not index_exists('store_item_visibility', 'uq_store_item_visibility_item_seat'):
            op.create_index(
                'uq_store_item_visibility_item_seat',
                'store_item_visibility',
                ['store_item_id', 'seat_id'],
                unique=True,
            )

    # entitlement_events.product_id back to Integer.
    if index_exists('entitlement_events', 'ix_entitlement_events_product_id'):
        op.drop_index('ix_entitlement_events_product_id', table_name='entitlement_events')
    if column_exists('entitlement_events', 'product_id'):
        op.execute("UPDATE entitlement_events SET product_id = NULL")
        op.alter_column(
            'entitlement_events',
            'product_id',
            existing_type=sa.String(length=36),
            type_=sa.Integer(),
            existing_nullable=True,
            postgresql_using='product_id::integer',
        )
