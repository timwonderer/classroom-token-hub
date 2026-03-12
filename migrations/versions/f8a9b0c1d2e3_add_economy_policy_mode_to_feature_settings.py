"""add economy policy mode to feature settings

Revision ID: f8a9b0c1d2e3
Revises: f163d7d7377a
Create Date: 2026-03-08 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8a9b0c1d2e3'
down_revision = 'f163d7d7377a'
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
    if not table_exists('feature_settings'):
        return

    if not column_exists('feature_settings', 'economy_policy_mode'):
        op.add_column('feature_settings', sa.Column('economy_policy_mode', sa.String(length=20), nullable=False, server_default='default'))
    if not column_exists('feature_settings', 'economy_policy_updated_at'):
        op.add_column('feature_settings', sa.Column('economy_policy_updated_at', sa.DateTime(timezone=True), nullable=True))
    if not column_exists('feature_settings', 'economy_policy_alignment_status'):
        op.add_column('feature_settings', sa.Column('economy_policy_alignment_status', sa.String(length=32), nullable=True))
    if not column_exists('feature_settings', 'economy_last_rebalanced_at'):
        op.add_column('feature_settings', sa.Column('economy_last_rebalanced_at', sa.DateTime(timezone=True), nullable=True))
    if not column_exists('feature_settings', 'economy_last_rebalanced_by'):
        op.add_column('feature_settings', sa.Column('economy_last_rebalanced_by', sa.Integer(), nullable=True))
    if not column_exists('feature_settings', 'economy_pending_rebalance_json'):
        op.add_column('feature_settings', sa.Column('economy_pending_rebalance_json', sa.Text(), nullable=True))

    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE feature_settings "
        "SET economy_policy_updated_at = CURRENT_TIMESTAMP "
        "WHERE economy_policy_updated_at IS NULL"
    ))

    inspector = sa.inspect(conn)
    columns = {col['name']: col for col in inspector.get_columns('feature_settings')}
    updated_at_column = columns.get('economy_policy_updated_at')
    if updated_at_column and updated_at_column.get('nullable', True):
        op.alter_column('feature_settings', 'economy_policy_updated_at', nullable=False)

    policy_mode_column = columns.get('economy_policy_mode')
    if policy_mode_column and policy_mode_column.get('default') is not None:
        op.alter_column('feature_settings', 'economy_policy_mode', server_default=None)


def downgrade():
    if not table_exists('feature_settings'):
        return

    if column_exists('feature_settings', 'economy_pending_rebalance_json'):
        op.drop_column('feature_settings', 'economy_pending_rebalance_json')
    if column_exists('feature_settings', 'economy_last_rebalanced_by'):
        op.drop_column('feature_settings', 'economy_last_rebalanced_by')
    if column_exists('feature_settings', 'economy_last_rebalanced_at'):
        op.drop_column('feature_settings', 'economy_last_rebalanced_at')
    if column_exists('feature_settings', 'economy_policy_alignment_status'):
        op.drop_column('feature_settings', 'economy_policy_alignment_status')
    if column_exists('feature_settings', 'economy_policy_updated_at'):
        op.drop_column('feature_settings', 'economy_policy_updated_at')
    if column_exists('feature_settings', 'economy_policy_mode'):
        op.drop_column('feature_settings', 'economy_policy_mode')
