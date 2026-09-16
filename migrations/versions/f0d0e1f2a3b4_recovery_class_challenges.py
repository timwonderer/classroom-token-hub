"""Frozen random recipients and persistent class confirmations."""
from alembic import op
import sqlalchemy as sa
revision = 'f0d0e1f2a3b4'
down_revision = 'e9c9d0e1f2a3'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    columns = {c['name'] for c in sa.inspect(bind).get_columns('recovery_requests')}
    for name, type_ in [('required_class_ids', sa.JSON()), ('attempt_nonce_hash', sa.String(64)), ('selection_started_at', sa.DateTime(timezone=True))]:
        if name not in columns:
            op.add_column('recovery_requests', sa.Column(name, type_, nullable=name != 'required_class_ids', server_default=sa.text("'[]'") if name == 'required_class_ids' else None))
    if 'submission_round' not in columns:
        op.add_column('recovery_requests', sa.Column('submission_round', sa.Integer(), nullable=False, server_default='0'))
    if 'issued_round' not in {c['name'] for c in sa.inspect(bind).get_columns('student_recovery_codes')}:
        op.add_column('student_recovery_codes', sa.Column('issued_round', sa.Integer(), nullable=True))
    if 'code_expires_at' not in {c['name'] for c in sa.inspect(bind).get_columns('student_recovery_codes')}:
        op.add_column('student_recovery_codes', sa.Column('code_expires_at', sa.DateTime(timezone=True), nullable=True))
    if 'recovery_class_challenges' not in sa.inspect(bind).get_table_names():
        op.create_table('recovery_class_challenges',
            sa.Column('recovery_request_id', sa.Integer(), sa.ForeignKey('recovery_requests.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.class_id', ondelete='CASCADE'), primary_key=True),
            sa.Column('proof_verified_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('selected_at', sa.DateTime(timezone=True)), sa.Column('selected_count', sa.Integer()),
            sa.Column('satisfied_at', sa.DateTime(timezone=True)),
            sa.Column('satisfied_round', sa.Integer()), sa.Column('received_round', sa.Integer()))

def downgrade():
    op.drop_table('recovery_class_challenges')
    op.drop_column('student_recovery_codes', 'code_expires_at')
    op.drop_column('student_recovery_codes', 'issued_round')
    op.drop_column('recovery_requests', 'submission_round')
    for name in ['required_class_ids', 'attempt_nonce_hash', 'selection_started_at']:
        op.drop_column('recovery_requests', name)
