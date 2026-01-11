"""create passkey credential tables v2

Revision ID: ed9de5ef6f79
Revises: 55f079e43ae6
Create Date: 2025-12-31 01:02:21.198065

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ed9de5ef6f79'
down_revision = '55f079e43ae6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Create admin_credentials table if it does not already exist
    if not inspector.has_table('admin_credentials'):
        op.create_table(
            'admin_credentials',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('admin_id', sa.Integer(), nullable=False),
            sa.Column('credential_id', sa.Text(), nullable=True),  # Optional: stored on passwordless.dev servers
            sa.Column('authenticator_name', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('last_used', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['admin_id'], ['admins.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )

    # Create system_admin_credentials table if it does not already exist
    if not inspector.has_table('system_admin_credentials'):
        op.create_table(
            'system_admin_credentials',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('system_admin_id', sa.Integer(), nullable=False),
            sa.Column('credential_id', sa.Text(), nullable=True),  # Optional: stored on passwordless.dev servers
            sa.Column('authenticator_name', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('last_used', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['system_admin_id'], ['system_admins.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )


def downgrade():
    # Drop tables if they exist (no indexes to drop since credential_id is not indexed here)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table('system_admin_credentials'):
        op.drop_table('system_admin_credentials')
    if inspector.has_table('admin_credentials'):
        op.drop_table('admin_credentials')
