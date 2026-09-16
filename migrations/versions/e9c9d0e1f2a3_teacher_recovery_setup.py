"""Server-owned teacher recovery setup authorization and encrypted progress."""
from alembic import op
import sqlalchemy as sa
revision = 'e9c9d0e1f2a3'
down_revision = 'd8b8c9d0e1f2'
branch_labels = None
depends_on = None

def upgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('recovery_requests')}
    for name, type_ in [('setup_nonce_hash', sa.String(64)), ('setup_totp_encrypted', sa.Text()), ('setup_username', sa.Text())]:
        if name not in columns:
            op.add_column('recovery_requests', sa.Column(name, type_, nullable=True))
    op.alter_column('recovery_requests', 'resume_new_username', type_=sa.Text())

def downgrade():
    for name in ['setup_nonce_hash', 'setup_totp_encrypted', 'setup_username']:
        op.drop_column('recovery_requests', name)
