"""Create join_codes anchor and add join_code_id foreign keys

Revision ID: 5b6c7d8e9f0a
Revises: 4a5b6c7d8e9f
Create Date: 2026-02-28 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone
import uuid


# revision identifiers, used by Alembic.
revision = '5b6c7d8e9f0a'
down_revision = '4a5b6c7d8e9f'
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


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk.get('name') for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def _add_join_code_id(table_name):
    if not table_exists(table_name):
        return
    if not column_exists(table_name, 'join_code_id'):
        op.add_column(table_name, sa.Column('join_code_id', sa.String(36), nullable=True))
    idx_name = f'ix_{table_name}_join_code_id'
    if not index_exists(table_name, idx_name):
        op.create_index(idx_name, table_name, ['join_code_id'], unique=False)


def _drop_join_code_id(table_name):
    if not table_exists(table_name):
        return
    idx_name = f'ix_{table_name}_join_code_id'
    if index_exists(table_name, idx_name):
        op.drop_index(idx_name, table_name=table_name)
    if column_exists(table_name, 'join_code_id'):
        op.drop_column(table_name, 'join_code_id')


def _create_fk(table_name, fk_name):
    if not table_exists(table_name):
        return
    if not column_exists(table_name, 'join_code_id'):
        return
    if not foreign_key_exists(table_name, fk_name):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.create_foreign_key(
                fk_name,
                'join_codes',
                ['join_code_id'],
                ['join_code_id'],
                ondelete='CASCADE',
            )


def _drop_fk(table_name, fk_name):
    if table_exists(table_name) and foreign_key_exists(table_name, fk_name):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_constraint(fk_name, type_='foreignkey')


def _student_fk_tables():
    return [
        ('teacher_blocks', 'fk_teacher_blocks_join_code_id_join_codes'),
        ('students', 'fk_students_join_code_id_join_codes'),
    ]


def _policy_fk_tables():
    return [
        ('banking_settings', 'fk_banking_settings_join_code_id_join_codes'),
        ('hall_pass_settings', 'fk_hall_pass_settings_join_code_id_join_codes'),
        ('insurance_policies', 'fk_insurance_policies_join_code_id_join_codes'),
        ('payroll_cache', 'fk_payroll_cache_join_code_id_join_codes'),
        ('payroll_settings', 'fk_payroll_settings_join_code_id_join_codes'),
        ('rent_settings', 'fk_rent_settings_join_code_id_join_codes'),
        ('rent_items', 'fk_rent_items_join_code_id_join_codes'),
        ('store_items', 'fk_store_items_join_code_id_join_codes'),
    ]


def _insert_join_code(conn, teacher_id, join_code_token):
    if teacher_id is None or not join_code_token:
        return
    existing = conn.execute(
        sa.text(
            """
            SELECT join_code_id FROM join_codes
            WHERE teacher_id = :teacher_id AND join_code_token = :join_code_token
            LIMIT 1
            """
        ),
        {'teacher_id': teacher_id, 'join_code_token': join_code_token},
    ).scalar()
    if existing:
        return

    conn.execute(
        sa.text(
            """
            INSERT INTO join_codes (
                join_code_id, join_code_token, teacher_id,
                is_active, is_archived, is_expired,
                expires_at, archived_at, metadata_json, created_at
            )
            VALUES (
                :join_code_id, :join_code_token, :teacher_id,
                :is_active, :is_archived, :is_expired,
                :expires_at, :archived_at, :metadata_json, :created_at
            )
            """
        ),
        {
            'join_code_id': str(uuid.uuid4()),
            'join_code_token': join_code_token,
            'teacher_id': teacher_id,
            'is_active': True,
            'is_archived': False,
            'is_expired': False,
            'expires_at': None,
            'archived_at': None,
            'metadata_json': None,
            'created_at': datetime.now(timezone.utc),
        },
    )


def _backfill_join_codes(conn):
    # Primary source of truth for (teacher, join_code) pairs.
    if table_exists('teacher_blocks'):
        rows = conn.execute(
            sa.text(
                """
                SELECT DISTINCT teacher_id, join_code
                FROM teacher_blocks
                WHERE teacher_id IS NOT NULL
                  AND join_code IS NOT NULL
                  AND join_code <> ''
                """
            )
        ).fetchall()
        for row in rows:
            _insert_join_code(conn, row[0], row[1])


def _map_by_teacher_and_code(table_name, teacher_col='teacher_id'):
    if not table_exists(table_name):
        return
    if not (column_exists(table_name, 'join_code_id') and column_exists(table_name, 'join_code') and column_exists(table_name, teacher_col)):
        return

    op.execute(
        sa.text(
            f"""
            UPDATE {table_name}
            SET join_code_id = (
                SELECT jc.join_code_id
                FROM join_codes jc
                WHERE jc.teacher_id = {table_name}.{teacher_col}
                  AND jc.join_code_token = {table_name}.join_code
                LIMIT 1
            )
            WHERE join_code_id IS NULL
              AND join_code IS NOT NULL
              AND {teacher_col} IS NOT NULL
            """
        )
    )


def _map_students_from_teacher_blocks():
    if not (table_exists('students') and table_exists('teacher_blocks')):
        return
    if not (column_exists('students', 'join_code_id') and column_exists('teacher_blocks', 'join_code_id')):
        return

    op.execute(
        sa.text(
            """
            UPDATE students
            SET join_code_id = (
                SELECT tb.join_code_id
                FROM teacher_blocks tb
                WHERE tb.student_id = students.id
                  AND tb.join_code_id IS NOT NULL
                ORDER BY tb.id ASC
                LIMIT 1
            )
            WHERE students.join_code_id IS NULL
            """
        )
    )


def upgrade():
    if not table_exists('join_codes'):
        op.create_table(
            'join_codes',
            sa.Column('join_code_id', sa.String(length=36), nullable=False),
            sa.Column('join_code_token', sa.String(length=20), nullable=False),
            sa.Column('teacher_id', sa.Integer(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('is_expired', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('metadata_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['teacher_id'], ['admins.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('join_code_id'),
            sa.UniqueConstraint('teacher_id', 'join_code_token', name='uq_join_codes_teacher_join_code_token'),
        )

    if not index_exists('join_codes', 'ix_join_codes_join_code_token'):
        op.create_index('ix_join_codes_join_code_token', 'join_codes', ['join_code_token'], unique=True)
    if not index_exists('join_codes', 'ix_join_codes_teacher_id'):
        op.create_index('ix_join_codes_teacher_id', 'join_codes', ['teacher_id'], unique=False)

    conn = op.get_bind()
    _backfill_join_codes(conn)

    for table_name, _fk in _student_fk_tables() + _policy_fk_tables():
        _add_join_code_id(table_name)

    # Backfill teacher_blocks first, then students transitively from blocks.
    if table_exists('teacher_blocks') and column_exists('teacher_blocks', 'teacher_id'):
        _map_by_teacher_and_code('teacher_blocks', 'teacher_id')

    _map_students_from_teacher_blocks()

    # Backfill class-level policy tables.
    _map_by_teacher_and_code('banking_settings', 'teacher_id')
    _map_by_teacher_and_code('hall_pass_settings', 'teacher_id')
    _map_by_teacher_and_code('insurance_policies', 'teacher_id')
    _map_by_teacher_and_code('payroll_settings', 'teacher_id')
    _map_by_teacher_and_code('rent_settings', 'teacher_id')
    _map_by_teacher_and_code('store_items', 'teacher_id')

    # Derive child policy tables transitively.
    if table_exists('rent_items') and column_exists('rent_items', 'rent_setting_id') and column_exists('rent_items', 'join_code_id'):
        op.execute(
            sa.text(
                """
                UPDATE rent_items
                SET join_code_id = (
                    SELECT rs.join_code_id
                    FROM rent_settings rs
                    WHERE rs.id = rent_items.rent_setting_id
                    LIMIT 1
                )
                WHERE join_code_id IS NULL
                """
            )
        )

    # payroll_cache currently keyed by teacher; only deterministic if one class exists.
    if table_exists('payroll_cache') and column_exists('payroll_cache', 'teacher_id') and column_exists('payroll_cache', 'join_code_id'):
        op.execute(
            sa.text(
                """
                UPDATE payroll_cache
                SET join_code_id = (
                    SELECT MIN(jc.join_code_id)
                    FROM join_codes jc
                    WHERE jc.teacher_id = payroll_cache.teacher_id
                    GROUP BY jc.teacher_id
                    HAVING COUNT(*) = 1
                )
                WHERE join_code_id IS NULL
                """
            )
        )

    for table_name, fk_name in _student_fk_tables() + _policy_fk_tables():
        _create_fk(table_name, fk_name)


def downgrade():
    for table_name, fk_name in reversed(_student_fk_tables() + _policy_fk_tables()):
        _drop_fk(table_name, fk_name)

    for table_name, _fk in reversed(_student_fk_tables() + _policy_fk_tables()):
        _drop_join_code_id(table_name)

    if table_exists('join_codes'):
        if index_exists('join_codes', 'ix_join_codes_teacher_id'):
            op.drop_index('ix_join_codes_teacher_id', table_name='join_codes')
        if index_exists('join_codes', 'ix_join_codes_join_code_token'):
            op.drop_index('ix_join_codes_join_code_token', table_name='join_codes')
        op.drop_table('join_codes')
