"""Drop eligible_for_reward from issues (DOM-SUP-001 v1.11)

The sysadmin bug reward was retired in DOM-SUP-001 v1.10 (owner ruling
2026-10-27, issue #1677). `issues.eligible_for_reward` has not been read or
set since: the resolve route ignores it and the views no longer receive it.
It was deliberately kept as a NOT NULL column with no database default
through v2.4.0 so existing INSERTs (which rely on the ORM's Python-side
default) kept working. This migration performs the deferred physical drop
authorized by that ruling (issue #1678).

Revision ID: 4fad9d362d0d
Revises: a0faf8b2a35d
Create Date: 2026-11-24 04:34:56.270514

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '4fad9d362d0d'
down_revision = 'a0faf8b2a35d'
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
        # Table doesn't exist
        return False


# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def upgrade():
    if table_exists('issues') and column_exists('issues', 'eligible_for_reward'):
        with op.batch_alter_table('issues', schema=None) as batch_op:
            batch_op.drop_column('eligible_for_reward')
        print("❌ Dropped issues.eligible_for_reward")
    else:
        print("⚠️  Column 'eligible_for_reward' does not exist on 'issues', skipping...")


def downgrade():
    if table_exists('issues') and not column_exists('issues', 'eligible_for_reward'):
        with op.batch_alter_table('issues', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    'eligible_for_reward',
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
        print("✅ Re-added issues.eligible_for_reward (default False)")
    else:
        print("⚠️  Column 'eligible_for_reward' already exists on 'issues', skipping...")
