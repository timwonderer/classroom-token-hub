"""Erase temporary claim material after student binding.

Authority: FEAT-IDEN-001 IV.3 and INV-ARC-019 X.
Deleted claim material is intentionally not reconstructed on downgrade.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c1a1b2d3e4f5'
down_revision = 'b4c5d6e7f8a9'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table('seats'):
        return
    bind.execute(sa.text("""
        UPDATE seats
        SET claim_first_name_hash = NULL, claim_last_name_hash = NULL,
            roster_fingerprint = NULL, dedupe_code = NULL
        WHERE role = 'student' AND user_id IS NOT NULL AND claimed_at IS NOT NULL
    """))


def downgrade():
    # Privacy cleanup is irreversible; do not recreate erased claim data.
    pass
