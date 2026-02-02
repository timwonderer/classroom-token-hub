"""Add join_code to deletion_request for join-code-centric scoping

Revision ID: e9a1b2c3d4f5
Revises: 62c2e19b2545
Create Date: 2026-02-01 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'e9a1b2c3d4f5'
down_revision = '62c2e19b2545'
branch_labels = None
depends_on = None


def column_exists(table, column):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns(table)]
    return column in columns


def upgrade():
    """Add join_code column to deletion_requests table and backfill from TeacherBlock."""

    # Add join_code column if it doesn't exist
    if not column_exists('deletion_requests', 'join_code'):
        with op.batch_alter_table('deletion_requests', schema=None) as batch_op:
            batch_op.add_column(sa.Column('join_code', sa.String(length=20), nullable=True))
            batch_op.create_index('ix_deletion_requests_join_code', ['join_code'], unique=False)
            batch_op.create_foreign_key(
                'fk_deletion_requests_join_code',
                'class_economies',
                ['join_code'],
                ['join_code'],
                ondelete='CASCADE'
            )

        # Backfill join_code from TeacherBlock based on admin_id and period match
        # For period deletion requests, match on teacher_id + block_name
        conn = op.get_bind()
        conn.execute(text("""
            UPDATE deletion_requests dr
            SET join_code = tb.join_code
            FROM teacher_blocks tb
            WHERE dr.request_type = 'period'
              AND dr.period IS NOT NULL
              AND dr.admin_id = tb.teacher_id
              AND dr.period = tb.block_name
              AND dr.join_code IS NULL
        """))

        # Note: Account deletion requests (request_type='account') keep join_code as NULL
        # since they're not scoped to a specific class period


def downgrade():
    """Remove join_code column from deletion_requests table."""

    if column_exists('deletion_requests', 'join_code'):
        with op.batch_alter_table('deletion_requests', schema=None) as batch_op:
            # Drop foreign key constraint first
            batch_op.drop_constraint('fk_deletion_requests_join_code', type_='foreignkey')
            # Drop index
            batch_op.drop_index('ix_deletion_requests_join_code')
            # Drop column
            batch_op.drop_column('join_code')
