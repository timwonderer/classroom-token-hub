"""Canonicalize obligation identity references — teacher_id → user_id

Renames legacy teacher/student FK references in obligation tables to canonical
user_id references targeting the users table:

- obligation_reversal.reversed_by_teacher_id → reversed_by_user_id (FK users.id)
- insurance_claims.processed_by_teacher_id → processed_by_user_id (FK users.id)
- insurance_claims.student_id dropped (seat_id is the canonical actor)
- insurance_claims.student_insurance_id FK repointed to insurance_enrollments.id

Revision ID: 0008a1b2c3d4
Revises: 9f7f970f28c3
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa

revision = '0008a1b2c3d4'
down_revision = '9f7f970f28c3'
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []


def upgrade():
    # --- obligation_reversal: reversed_by_teacher_id → reversed_by_user_id ---
    if table_exists('obligation_reversal'):
        # Drop old FK
        for fk in get_foreign_keys_by_column('obligation_reversal', 'reversed_by_teacher_id'):
            if fk.get('name'):
                op.drop_constraint(fk['name'], 'obligation_reversal', type_='foreignkey')

        if column_exists('obligation_reversal', 'reversed_by_teacher_id'):
            if not column_exists('obligation_reversal', 'reversed_by_user_id'):
                op.alter_column('obligation_reversal', 'reversed_by_teacher_id',
                                new_column_name='reversed_by_user_id')
            else:
                op.drop_column('obligation_reversal', 'reversed_by_teacher_id')

        if column_exists('obligation_reversal', 'reversed_by_user_id'):
            op.create_foreign_key(
                'fk_obligation_reversal_reversed_by_user',
                'obligation_reversal', 'users',
                ['reversed_by_user_id'], ['id'],
                ondelete='SET NULL',
            )

    # --- insurance_claims: processed_by_teacher_id → processed_by_user_id ---
    if table_exists('insurance_claims'):
        for fk in get_foreign_keys_by_column('insurance_claims', 'processed_by_teacher_id'):
            if fk.get('name'):
                op.drop_constraint(fk['name'], 'insurance_claims', type_='foreignkey')

        if column_exists('insurance_claims', 'processed_by_teacher_id'):
            if not column_exists('insurance_claims', 'processed_by_user_id'):
                op.alter_column('insurance_claims', 'processed_by_teacher_id',
                                new_column_name='processed_by_user_id')
            else:
                op.drop_column('insurance_claims', 'processed_by_teacher_id')

        if column_exists('insurance_claims', 'processed_by_user_id'):
            op.create_foreign_key(
                'fk_insurance_claims_processed_by_user',
                'insurance_claims', 'users',
                ['processed_by_user_id'], ['id'],
                ondelete='SET NULL',
            )

        # --- insurance_claims: drop student_id (seat_id is canonical actor) ---
        for fk in get_foreign_keys_by_column('insurance_claims', 'student_id'):
            if fk.get('name'):
                op.drop_constraint(fk['name'], 'insurance_claims', type_='foreignkey')

        if column_exists('insurance_claims', 'student_id'):
            op.drop_column('insurance_claims', 'student_id')

        # --- insurance_claims: repoint student_insurance_id FK to insurance_enrollments ---
        for fk in get_foreign_keys_by_column('insurance_claims', 'student_insurance_id'):
            if fk.get('name'):
                op.drop_constraint(fk['name'], 'insurance_claims', type_='foreignkey')

        if column_exists('insurance_claims', 'student_insurance_id'):
            op.alter_column('insurance_claims', 'student_insurance_id',
                            new_column_name='enrollment_id')

        if column_exists('insurance_claims', 'enrollment_id'):
            op.create_foreign_key(
                'fk_insurance_claims_enrollment',
                'insurance_claims', 'insurance_enrollments',
                ['enrollment_id'], ['id'],
            )


def downgrade():
    if table_exists('insurance_claims'):
        for fk in get_foreign_keys_by_column('insurance_claims', 'enrollment_id'):
            if fk.get('name'):
                op.drop_constraint(fk['name'], 'insurance_claims', type_='foreignkey')

        if column_exists('insurance_claims', 'enrollment_id'):
            op.alter_column('insurance_claims', 'enrollment_id',
                            new_column_name='student_insurance_id')

        if column_exists('insurance_claims', 'student_insurance_id'):
            op.create_foreign_key(
                'insurance_claims_student_insurance_id_fkey',
                'insurance_claims', 'student_insurance',
                ['student_insurance_id'], ['id'],
            )

        if not column_exists('insurance_claims', 'student_id'):
            op.add_column('insurance_claims', sa.Column(
                'student_id', sa.Integer(),
                sa.ForeignKey('students.id'), nullable=True,
            ))

        for fk in get_foreign_keys_by_column('insurance_claims', 'processed_by_user_id'):
            if fk.get('name'):
                op.drop_constraint(fk['name'], 'insurance_claims', type_='foreignkey')

        if column_exists('insurance_claims', 'processed_by_user_id'):
            op.alter_column('insurance_claims', 'processed_by_user_id',
                            new_column_name='processed_by_teacher_id')

        if column_exists('insurance_claims', 'processed_by_teacher_id'):
            op.create_foreign_key(
                'insurance_claims_processed_by_teacher_id_fkey',
                'insurance_claims', 'teachers',
                ['processed_by_teacher_id'], ['id'],
            )

    if table_exists('obligation_reversal'):
        for fk in get_foreign_keys_by_column('obligation_reversal', 'reversed_by_user_id'):
            if fk.get('name'):
                op.drop_constraint(fk['name'], 'obligation_reversal', type_='foreignkey')

        if column_exists('obligation_reversal', 'reversed_by_user_id'):
            op.alter_column('obligation_reversal', 'reversed_by_user_id',
                            new_column_name='reversed_by_teacher_id')

        if column_exists('obligation_reversal', 'reversed_by_teacher_id'):
            op.create_foreign_key(
                'obligation_reversal_reversed_by_teacher_id_fkey',
                'obligation_reversal', 'teachers',
                ['reversed_by_teacher_id'], ['id'],
                ondelete='SET NULL',
            )
