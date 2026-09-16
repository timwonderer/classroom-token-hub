"""Encrypted PII staging for signup; no plaintext or existing-row conversion."""
from alembic import op
import sqlalchemy as sa
revision = 'a1e1f2a3b4c5'
down_revision = 'f0d0e1f2a3b4'
branch_labels = None
depends_on = None


def upgrade():
    # Initial migration bootstraps from current metadata.
    if 'teacher_signup_attempts' not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table('teacher_signup_attempts',
            sa.Column('nonce_hash', sa.String(64), primary_key=True),
            sa.Column('payload_encrypted', sa.Text(), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False))
        op.create_index('ix_teacher_signup_attempts_expires_at', 'teacher_signup_attempts', ['expires_at'])


def downgrade():
    op.drop_table('teacher_signup_attempts')
