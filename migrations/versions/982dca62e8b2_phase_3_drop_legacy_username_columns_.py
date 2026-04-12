"""Phase 3: Drop legacy username columns and legacy transition fields

Revision ID: 982dca62e8b2
Revises: c5a7dedeca47
Create Date: 2026-04-12 02:20:00.835834

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '982dca62e8b2'
down_revision = 'c5a7dedeca47'
branch_labels = None
depends_on = None


def upgrade():
    # --- STUDENTS (V1 Shadow Drop) ---
    with op.batch_alter_table('students', schema=None) as batch_op:
        if 'shadow_for_admin_id' in [col['name'] for col in sa.inspect(op.get_bind()).get_columns('students')]:
            batch_op.drop_index('ix_students_shadow_for_admin_id')
            batch_op.drop_constraint('students_shadow_for_admin_id_fkey', type_='foreignkey')
            batch_op.drop_column('is_teacher_shadow')
            batch_op.drop_column('shadow_for_admin_id')

    # --- SYSTEM ADMINS (Legacy Username Drop) ---
    with op.batch_alter_table('system_admins', schema=None) as batch_op:
        if 'username' in [col['name'] for col in sa.inspect(op.get_bind()).get_columns('system_admins')]:
            batch_op.drop_constraint('system_admins_username_key', type_='unique')
            batch_op.create_unique_constraint('uq_system_admins_username_hash', ['username_hash'])
            batch_op.drop_column('username')

    # --- TEACHERS (Legacy Username Drop) ---
    with op.batch_alter_table('teachers', schema=None) as batch_op:
        if 'username' in [col['name'] for col in sa.inspect(op.get_bind()).get_columns('teachers')]:
            batch_op.drop_constraint('teachers_username_key', type_='unique')
            batch_op.create_unique_constraint('uq_teachers_username_hash', ['username_hash'])
            batch_op.drop_column('username')

    # --- TRANSACTION (Orphaned Actor Membership Drop) ---
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        if 'actor_membership_id' in [col['name'] for col in sa.inspect(op.get_bind()).get_columns('transaction')]:
            batch_op.drop_index('ix_transaction_actor_membership_id')
            batch_op.drop_constraint('transaction_actor_membership_id_fkey', type_='foreignkey')
            batch_op.drop_column('actor_membership_id')

    # --- HALL PASS LOGS (Orphaned Actor Membership Drop) ---
    with op.batch_alter_table('hall_pass_logs', schema=None) as batch_op:
        if 'actor_membership_id' in [col['name'] for col in sa.inspect(op.get_bind()).get_columns('hall_pass_logs')]:
            batch_op.drop_index('ix_hall_pass_logs_actor_membership_id')
            batch_op.drop_constraint('hall_pass_logs_actor_membership_id_fkey', type_='foreignkey')
            batch_op.drop_column('actor_membership_id')


def downgrade():
    # --- HALL PASS LOGS ---
    with op.batch_alter_table('hall_pass_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('actor_membership_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.create_foreign_key('hall_pass_logs_actor_membership_id_fkey', 'class_memberships', ['actor_membership_id'], ['id'], ondelete='SET NULL')
        batch_op.create_index('ix_hall_pass_logs_actor_membership_id', ['actor_membership_id'], unique=False)

    # --- TRANSACTION ---
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.add_column(sa.Column('actor_membership_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.create_foreign_key('transaction_actor_membership_id_fkey', 'class_memberships', ['actor_membership_id'], ['id'], ondelete='SET NULL')
        batch_op.create_index('ix_transaction_actor_membership_id', ['actor_membership_id'], unique=False)

    # --- TEACHERS ---
    with op.batch_alter_table('teachers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('username', sa.VARCHAR(length=80), autoincrement=False, nullable=True))
        batch_op.drop_constraint('uq_teachers_username_hash', type_='unique')
        batch_op.create_unique_constraint('teachers_username_key', ['username'])

    # --- SYSTEM ADMINS ---
    with op.batch_alter_table('system_admins', schema=None) as batch_op:
        batch_op.add_column(sa.Column('username', sa.VARCHAR(length=80), autoincrement=False, nullable=True))
        batch_op.drop_constraint('uq_system_admins_username_hash', type_='unique')
        batch_op.create_unique_constraint('system_admins_username_key', ['username'])

    # --- STUDENTS ---
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('shadow_for_admin_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('is_teacher_shadow', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False))
        batch_op.create_foreign_key('students_shadow_for_admin_id_fkey', 'teachers', ['shadow_for_admin_id'], ['id'], ondelete='CASCADE')
        batch_op.create_index('ix_students_shadow_for_admin_id', ['shadow_for_admin_id'], unique=True)
