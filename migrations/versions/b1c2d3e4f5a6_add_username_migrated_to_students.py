"""Add username_migrated to students

Revision ID: b1c2d3e4f5a6
Revises: 9845e9a9baca
Create Date: 2026-04-12 00:00:00.000000

Adds a boolean flag to the students table that tracks whether the student's
username uses the new PII-free format (random 4-digit suffix) vs the legacy
format that embedded dob_sum.

Existing students get False (need the one-time migration flow on next login).
New students get True automatically from the create_username route.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = '9845e9a9baca'
branch_labels = None
depends_on = None


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
    if not column_exists('students', 'username_migrated'):
        op.add_column(
            'students',
            sa.Column(
                'username_migrated',
                sa.Boolean(),
                nullable=False,
                server_default='false',
            ),
        )
        print("✅ Added username_migrated column to students (default false for all existing rows)")
    else:
        print("⚠️  Column 'username_migrated' already exists on 'students', skipping")


def downgrade():
    if column_exists('students', 'username_migrated'):
        op.drop_column('students', 'username_migrated')
        print("❌ Dropped username_migrated column from students")
    else:
        print("⚠️  Column 'username_migrated' does not exist on 'students', skipping")
