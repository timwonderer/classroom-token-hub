"""Bind support snapshot lifetime to its originating seat (DOM-SUP-001 X).

Validate existing references; never infer identity or silently delete old tickets.
"""
from alembic import op
import sqlalchemy as sa

revision = 'e3c3d4e5f6a7'
down_revision = 'd2b2c3d4e5f6'
branch_labels = None
depends_on = None
_NAME = 'fk_issues_actor_public_id_seats'


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('issues'):
        return
    with op.batch_alter_table('issues') as batch:
        batch.alter_column('class_public_id', existing_type=sa.String(36), nullable=False)
        if _NAME not in {fk['name'] for fk in inspector.get_foreign_keys('issues')}:
            batch.create_foreign_key(_NAME, 'seats', ['actor_public_id'], ['public_id'], ondelete='CASCADE')


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('issues') and _NAME in {fk['name'] for fk in inspector.get_foreign_keys('issues')}:
        with op.batch_alter_table('issues') as batch:
            batch.drop_constraint(_NAME, type_='foreignkey')
            batch.alter_column('class_public_id', existing_type=sa.String(36), nullable=True)
