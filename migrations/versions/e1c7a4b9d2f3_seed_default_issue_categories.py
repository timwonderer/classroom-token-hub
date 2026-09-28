"""Seed the default issue categories at install.

Categories are system-managed reference data (DOM-SUP-001 §issue_categories):
students and teachers pick from them, and nobody creates them at runtime. They
were only ever inserted as a side effect of rendering the student help page or
the teacher issues queue, which is a write in a GET handler (INV-ARC-007).
Production, rebuilt from an empty schema at launch, had rendered neither, so the
table was empty and every teacher ticket raised on a missing category.

The data is written here literally rather than imported from app code: a
migration must replay the same way in the future, whatever the app says then.
Adds the three teacher support categories (General question, Bug report,
Feature request).

Revision ID: e1c7a4b9d2f3
Revises: d7a3e9b1c5f2
Create Date: 2026-09-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1c7a4b9d2f3'
down_revision = 'd7a3e9b1c5f2'
branch_labels = None
depends_on = None


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


# (name, description, category_type, display_order)
DEFAULT_CATEGORIES = (
    ('Incorrect Amount', 'The transaction amount is wrong', 'transaction', 1),
    ('Duplicate Transaction', 'This transaction appears twice', 'transaction', 2),
    ('Wrong Account', 'Transaction went to wrong account (checking vs savings)', 'transaction', 3),
    ('Timing Issue', 'Transaction happened at wrong time or date', 'transaction', 4),
    ('Incorrect Charge/Fee', 'I was charged incorrectly', 'transaction', 5),
    ('Missing Payment', "I should have been paid but wasn't", 'transaction', 6),
    ('Clock In/Out Not Working', 'Unable to clock in or clock out', 'general', 1),
    ('Balance Incorrect', "My balance doesn't make sense", 'general', 2),
    ('Feature Not Working', "Something on the site isn't working", 'general', 3),
    ('Cannot Purchase Item', 'Unable to buy from store', 'general', 4),
    ('Missing Job/Assignment', 'My job disappeared or changed', 'general', 5),
    ('General question', 'A question about using Classroom Token Hub', 'general', 10),
    ('Bug report', 'Something in Classroom Token Hub is broken', 'general', 11),
    ('Feature request', 'An idea for something Classroom Token Hub should do', 'general', 12),
    ('Other Issue', 'Something else is wrong', 'general', 99),
)


def upgrade():
    if not table_exists('issue_categories'):
        print("⚠️  Table 'issue_categories' does not exist, skipping seed...")
        return
    conn = op.get_bind()
    inserted = 0
    for name, description, category_type, display_order in DEFAULT_CATEGORIES:
        result = conn.execute(
            sa.text(
                "INSERT INTO issue_categories"
                " (name, description, category_type, is_active, display_order, created_at)"
                " VALUES (:name, :description, :category_type, true, :display_order, now())"
                " ON CONFLICT (name) DO NOTHING"
            ),
            {
                "name": name,
                "description": description,
                "category_type": category_type,
                "display_order": display_order,
            },
        )
        inserted += result.rowcount or 0
    print(f"✅ Seeded {inserted} issue categories ({len(DEFAULT_CATEGORIES) - inserted} already present)")


def downgrade():
    # Deliberately a no-op. ON CONFLICT DO NOTHING means some of these rows may
    # have existed before this revision (seeded by the old GET handlers), and
    # nothing records which ones this revision inserted. Deleting by name could
    # remove categories that predate it. Leftover reference rows are harmless
    # to the previous revision, which reads this table the same way.
    print("⚠️  Leaving issue categories in place; they are reference data")
