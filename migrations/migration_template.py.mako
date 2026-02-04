"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
#
# These helper functions ensure migrations can be run multiple times without
# errors. This is critical for production deployments where:
# 1. Schema changes may have been applied manually to fix urgent issues
# 2. Previous migration runs may have partially completed before failing
# 3. The same migration may exist in multiple branches that get merged
#
# Reference: docs/development/MIGRATION_BEST_PRACTICES.md
# ============================================================================

def table_exists(table_name):
    """Check if a table exists.

    Args:
        table_name: Name of the table to check

    Returns:
        bool: True if table exists, False otherwise
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table.

    Args:
        table_name: Name of the table
        column_name: Name of the column to check

    Returns:
        bool: True if column exists, False otherwise
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        # Table doesn't exist
        return False


def index_exists(table_name, index_name):
    """Check if an index exists on a table.

    Args:
        table_name: Name of the table
        index_name: Name of the index to check

    Returns:
        bool: True if index exists, False otherwise
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        # Table doesn't exist
        return False


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key constraint exists on a table.

    Args:
        table_name: Name of the table
        fk_name: Name of the foreign key to check

    Returns:
        bool: True if foreign key exists, False otherwise
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        # Table doesn't exist
        return False


def constraint_exists(table_name, constraint_name):
    """Check if a unique constraint exists on a table.

    Args:
        table_name: Name of the table
        constraint_name: Name of the constraint to check

    Returns:
        bool: True if constraint exists, False otherwise
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        constraints = [c['name'] for c in inspector.get_unique_constraints(table_name)]
        return constraint_name in constraints
    except Exception:
        # Table doesn't exist
        return False


def get_foreign_keys_by_column(table_name, column_name):
    """Get foreign key constraints that reference a specific column.

    Use this in downgrade() instead of hardcoding FK names, which vary
    across environments and can cause migration failures.

    Example:
        # Instead of:
        # op.drop_constraint('students_teacher_id_fkey', 'students', type_='foreignkey')

        # Use:
        for fk in get_foreign_keys_by_column('students', 'teacher_id'):
            op.drop_constraint(fk['name'], 'students', type_='foreignkey')

    Args:
        table_name: Name of the table
        column_name: Name of the column

    Returns:
        list: List of foreign key constraint dicts
    """
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
    # Example patterns:

    # 1. Creating a table (check if exists first)
    # if not table_exists('new_table'):
    #     op.create_table(
    #         'new_table',
    #         sa.Column('id', sa.Integer(), nullable=False),
    #         sa.Column('name', sa.String(100), nullable=False),
    #         sa.PrimaryKeyConstraint('id')
    #     )
    #     print("✅ Created new_table")
    # else:
    #     print("⚠️  Table 'new_table' already exists, skipping...")

    # 2. Adding a column (check if exists first)
    # if not column_exists('existing_table', 'new_column'):
    #     with op.batch_alter_table('existing_table', schema=None) as batch_op:
    #         batch_op.add_column(sa.Column('new_column', sa.String(100), nullable=True))
    #     print("✅ Added new_column to existing_table")
    # else:
    #     print("⚠️  Column 'new_column' already exists on 'existing_table', skipping...")

    # 3. Creating an index (check if exists first)
    # if not index_exists('existing_table', 'ix_existing_table_new_column'):
    #     op.create_index('ix_existing_table_new_column', 'existing_table', ['new_column'])
    #     print("✅ Created index ix_existing_table_new_column")
    # else:
    #     print("⚠️  Index 'ix_existing_table_new_column' already exists, skipping...")

    # 4. Creating a foreign key (check if exists first)
    # if not foreign_key_exists('child_table', 'fk_child_parent'):
    #     with op.batch_alter_table('child_table', schema=None) as batch_op:
    #         batch_op.create_foreign_key('fk_child_parent', 'parent_table', ['parent_id'], ['id'])
    #     print("✅ Created foreign key fk_child_parent")
    # else:
    #     print("⚠️  Foreign key 'fk_child_parent' already exists, skipping...")

    # 5. Backfilling data (always safe to run multiple times with WHERE clause)
    # conn = op.get_bind()
    # conn.execute(sa.text(
    #     "UPDATE existing_table SET new_column = 'default' WHERE new_column IS NULL"
    # ))

    # 6. Making a column NOT NULL (check if already NOT NULL)
    # inspector = sa.inspect(op.get_bind())
    # columns = inspector.get_columns('existing_table')
    # column = next((col for col in columns if col['name'] == 'new_column'), None)
    # if column and column.get('nullable', True):
    #     with op.batch_alter_table('existing_table', schema=None) as batch_op:
    #         batch_op.alter_column('new_column', nullable=False)
    #     print("✅ Set new_column to NOT NULL")
    # else:
    #     print("⚠️  Column 'new_column' is already NOT NULL, skipping...")

    pass


def downgrade():
    # Example patterns:

    # 1. Dropping a foreign key (use dynamic discovery, not hardcoded name)
    # for fk in get_foreign_keys_by_column('child_table', 'parent_id'):
    #     with op.batch_alter_table('child_table', schema=None) as batch_op:
    #         batch_op.drop_constraint(fk['name'], type_='foreignkey')
    #     print(f"❌ Dropped foreign key {fk['name']}")

    # 2. Dropping an index (check if exists first)
    # if index_exists('existing_table', 'ix_existing_table_new_column'):
    #     op.drop_index('ix_existing_table_new_column', table_name='existing_table')
    #     print("❌ Dropped index ix_existing_table_new_column")
    # else:
    #     print("⚠️  Index 'ix_existing_table_new_column' does not exist, skipping...")

    # 3. Dropping a column (check if exists first)
    # if column_exists('existing_table', 'new_column'):
    #     with op.batch_alter_table('existing_table', schema=None) as batch_op:
    #         batch_op.drop_column('new_column')
    #     print("❌ Dropped new_column from existing_table")
    # else:
    #     print("⚠️  Column 'new_column' does not exist on 'existing_table', skipping...")

    # 4. Dropping a table (check if exists first)
    # if table_exists('new_table'):
    #     op.drop_table('new_table')
    #     print("❌ Dropped table new_table")
    # else:
    #     print("⚠️  Table 'new_table' does not exist, skipping...")

    pass
