"""Drop obsolete deletion_requests table

Revision ID: h9i0j1k2l3m4
Revises: 1adc6456ab0e, f8a9b0c1d2e3
Create Date: 2026-03-09 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h9i0j1k2l3m4'
down_revision = ('1adc6456ab0e', 'f8a9b0c1d2e3')
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade():
    conn = op.get_bind()

    if table_exists('deletion_requests'):
        op.drop_table('deletion_requests')

    if conn.dialect.name == 'postgresql':
        conn.execute(sa.text("DROP TYPE IF EXISTS deletionrequeststatus CASCADE"))
        conn.execute(sa.text("DROP TYPE IF EXISTS deletionrequesttype CASCADE"))


def downgrade():
    conn = op.get_bind()

    if conn.dialect.name == 'postgresql':
        conn.execute(sa.text(
            "CREATE TYPE deletionrequesttype AS ENUM ('period', 'account')"
        ))
        conn.execute(sa.text(
            "CREATE TYPE deletionrequeststatus AS ENUM ('pending', 'approved', 'rejected')"
        ))
        request_type_type = sa.Enum(name='deletionrequesttype')
        status_type = sa.Enum(name='deletionrequeststatus')
    else:
        request_type_type = sa.String(length=20)
        status_type = sa.String(length=20)

    if not table_exists('deletion_requests'):
        op.create_table(
            'deletion_requests',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('teacher_id', sa.Integer(), nullable=False),
            sa.Column('join_code', sa.String(length=20), nullable=True),
            sa.Column('request_type', request_type_type, nullable=False),
            sa.Column('period', sa.String(length=10), nullable=True),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('status', status_type, nullable=False),
            sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('resolved_by', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['resolved_by'], ['system_admins.id'], ondelete='NO ACTION'),
            sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_deletion_requests_status', 'deletion_requests', ['status'], unique=False)
        op.create_index('ix_deletion_requests_teacher_id', 'deletion_requests', ['teacher_id'], unique=False)
