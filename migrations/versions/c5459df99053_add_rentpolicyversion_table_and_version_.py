"""Add RentPolicyVersion table and version tracking to RentSettings and ObligationAssessment

Revision ID: c5459df99053
Revises: 0008a1b2c3d4
Create Date: 2026-06-13 21:24:30.604479

"""
from alembic import op
import sqlalchemy as sa

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
    """Check if a foreign key exists on a table."""
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

# revision identifiers, used by Alembic.
revision = 'c5459df99053'
down_revision = '0008a1b2c3d4'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create rent_policy_versions table
    if not table_exists('rent_policy_versions'):
        op.create_table('rent_policy_versions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('class_id', sa.String(length=36), nullable=False),
            sa.Column('version_number', sa.Integer(), nullable=False),
            sa.Column('source_rent_setting_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('rent_amount', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('frequency_type', sa.String(length=20), nullable=False),
            sa.Column('custom_frequency_value', sa.Integer(), nullable=True),
            sa.Column('custom_frequency_unit', sa.String(length=20), nullable=True),
            sa.Column('due_day_of_month', sa.Integer(), nullable=True),
            sa.Column('cycle_length_days', sa.Integer(), nullable=False),
            sa.Column('grace_period_days', sa.Integer(), nullable=False),
            sa.Column('late_penalty_amount', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('late_penalty_type', sa.String(length=20), nullable=False),
            sa.Column('late_penalty_frequency_days', sa.Integer(), nullable=True),
            sa.Column('bill_preview_enabled', sa.Boolean(), nullable=False),
            sa.Column('bill_preview_days', sa.Integer(), nullable=False),
            sa.Column('allow_incremental_payment', sa.Boolean(), nullable=False),
            sa.Column('prevent_purchase_when_late', sa.Boolean(), nullable=False),
            sa.Column('frozen_items', sa.JSON(), nullable=False),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['source_rent_setting_id'], ['rent_settings.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        print("✅ Created rent_policy_versions table")
    else:
        print("⚠️  Table rent_policy_versions already exists, skipping...")

    if not index_exists('rent_policy_versions', 'ix_rent_policy_versions_class_id'):
        op.create_index(op.f('ix_rent_policy_versions_class_id'), 'rent_policy_versions', ['class_id'], unique=False)

    if not index_exists('rent_policy_versions', 'ix_rent_policy_versions_class_version'):
        op.create_index('ix_rent_policy_versions_class_version', 'rent_policy_versions', ['class_id', 'version_number'], unique=False)

    # 2. Add version tracking columns to rent_settings
    if not column_exists('rent_settings', 'active_version_id'):
        op.add_column('rent_settings', sa.Column('active_version_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_rent_settings_active_version_id',
            'rent_settings', 'rent_policy_versions',
            ['active_version_id'], ['id'],
            ondelete='SET NULL',
        )
        print("✅ Added active_version_id to rent_settings")

    if not column_exists('rent_settings', 'next_version_id'):
        op.add_column('rent_settings', sa.Column('next_version_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_rent_settings_next_version_id',
            'rent_settings', 'rent_policy_versions',
            ['next_version_id'], ['id'],
            ondelete='SET NULL',
        )
        print("✅ Added next_version_id to rent_settings")

    # 3. Add rent_policy_version_id to assessment_events
    if not column_exists('assessment_events', 'rent_policy_version_id'):
        op.add_column('assessment_events', sa.Column('rent_policy_version_id', sa.Integer(), nullable=True))
        op.create_index(
            op.f('ix_assessment_events_rent_policy_version_id'),
            'assessment_events', ['rent_policy_version_id'], unique=False,
        )
        op.create_foreign_key(
            'fk_assessment_events_rent_policy_version_id',
            'assessment_events', 'rent_policy_versions',
            ['rent_policy_version_id'], ['id'],
            ondelete='SET NULL',
        )
        print("✅ Added rent_policy_version_id to assessment_events")


def downgrade():
    # 1. Remove rent_policy_version_id from assessment_events
    for fk in get_foreign_keys_by_column('assessment_events', 'rent_policy_version_id'):
        if fk.get('name'):
            op.drop_constraint(fk['name'], 'assessment_events', type_='foreignkey')
    if index_exists('assessment_events', 'ix_assessment_events_rent_policy_version_id'):
        op.drop_index(op.f('ix_assessment_events_rent_policy_version_id'), table_name='assessment_events')
    if column_exists('assessment_events', 'rent_policy_version_id'):
        op.drop_column('assessment_events', 'rent_policy_version_id')
        print("❌ Dropped rent_policy_version_id from assessment_events")

    # 2. Remove version tracking from rent_settings
    for col_name in ('next_version_id', 'active_version_id'):
        for fk in get_foreign_keys_by_column('rent_settings', col_name):
            if fk.get('name'):
                op.drop_constraint(fk['name'], 'rent_settings', type_='foreignkey')
        if column_exists('rent_settings', col_name):
            op.drop_column('rent_settings', col_name)

    print("❌ Dropped version tracking columns from rent_settings")

    # 3. Drop rent_policy_versions table
    if index_exists('rent_policy_versions', 'ix_rent_policy_versions_class_version'):
        op.drop_index('ix_rent_policy_versions_class_version', table_name='rent_policy_versions')
    if index_exists('rent_policy_versions', 'ix_rent_policy_versions_class_id'):
        op.drop_index(op.f('ix_rent_policy_versions_class_id'), table_name='rent_policy_versions')
    if table_exists('rent_policy_versions'):
        op.drop_table('rent_policy_versions')
        print("❌ Dropped rent_policy_versions table")
