"""Replace plaintext dob_sum with dob_sum_hash in teacher_blocks

Revision ID: b8c9d0e1f2a3
Revises: c9d8e7f6a5b4
Create Date: 2026-03-02

Replaces the plaintext integer dob_sum column on teacher_blocks with a
dob_sum_hash column (HMAC-SHA256). Existing rows are migrated in-place:
the current dob_sum value is hashed using HMAC(pepper, salt + str(dob_sum)).
If plaintext rows still exist, PEPPER_KEY must be present or migration aborts.
"""
from alembic import op
import sqlalchemy as sa
import hmac
import hashlib
import os


# revision identifiers, used by Alembic.
revision = 'b8c9d0e1f2a3'
down_revision = 'c9d8e7f6a5b4'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('teacher_blocks')}

    # Add the new dob_sum_hash column
    if 'dob_sum_hash' not in cols:
        op.add_column(
            'teacher_blocks',
            sa.Column('dob_sum_hash', sa.String(length=64), nullable=True)
        )

    # Migrate existing plaintext dob_sum values to hashed form
    if 'dob_sum' in cols:
        teacher_blocks_table = sa.Table(
            'teacher_blocks', sa.MetaData(), autoload_with=bind
        )
        rows_requiring_hash = bind.execute(
            sa.select(sa.func.count()).select_from(teacher_blocks_table).where(
                teacher_blocks_table.c.dob_sum.is_not(None),
                teacher_blocks_table.c.salt.is_not(None),
            )
        ).scalar_one()

        pepper_str = os.environ.get('PEPPER_KEY')
        if rows_requiring_hash and not pepper_str:
            raise RuntimeError(
                "PEPPER_KEY must be set before migrating teacher_blocks.dob_sum to dob_sum_hash."
            )

        if pepper_str:
            pepper = pepper_str.encode()
            rows = bind.execute(
                sa.select(
                    teacher_blocks_table.c.id,
                    teacher_blocks_table.c.dob_sum,
                    teacher_blocks_table.c.salt,
                )
            ).fetchall()

            for row_id, dob_sum_val, salt_val in rows:
                if dob_sum_val is not None and salt_val is not None:
                    dob_sum_bytes = str(dob_sum_val).encode()
                    h = hmac.new(pepper, salt_val + dob_sum_bytes, hashlib.sha256).hexdigest()
                    bind.execute(
                        teacher_blocks_table.update()
                        .where(teacher_blocks_table.c.id == row_id)
                        .values(dob_sum_hash=h)
                    )

        # Drop the old plaintext column
        op.drop_column('teacher_blocks', 'dob_sum')


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('teacher_blocks')}

    if 'dob_sum' not in cols:
        op.add_column(
            'teacher_blocks',
            sa.Column('dob_sum', sa.Integer(), nullable=True)
        )

    if 'dob_sum_hash' in cols:
        op.drop_column('teacher_blocks', 'dob_sum_hash')
