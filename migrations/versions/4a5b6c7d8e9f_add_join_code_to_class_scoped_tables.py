"""Add join_code to class-scoped tables

Revision ID: 4a5b6c7d8e9f
Revises: 3d54e2e343df
Create Date: 2026-02-28 11:00:00.000000

Adds `join_code` columns to teacher/student/class-scoped tables so class tenancy
can be enforced at the join-code boundary instead of teacher-only scope.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a5b6c7d8e9f'
down_revision = '3d54e2e343df'
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


def _add_join_code(table_name):
    if not table_exists(table_name):
        return
    if not column_exists(table_name, 'join_code'):
        op.add_column(table_name, sa.Column('join_code', sa.String(20), nullable=True))
    idx = f'ix_{table_name}_join_code'
    if not index_exists(table_name, idx):
        op.create_index(idx, table_name, ['join_code'], unique=False)


def _drop_join_code(table_name):
    if not table_exists(table_name):
        return
    idx = f'ix_{table_name}_join_code'
    if index_exists(table_name, idx):
        op.drop_index(idx, table_name=table_name)
    if column_exists(table_name, 'join_code'):
        op.drop_column(table_name, 'join_code')


def upgrade():
    # Class-scoped or teacher-owned tables that must support join-code tenancy.
    tables = [
        'banking_settings',
        'contract_job_claims',
        'deletion_requests',
        'demo_students',
        'employee_job_assignments',
        'employee_job_warnings',
        'hall_pass_settings',
        'insurance_claims',
        'insurance_policies',
        'insurance_policy_blocks',
        'issue_resolution_actions',
        'issue_status_history',
        'job_applications',
        'job_templates',
        'jobs_settings',
        'payroll_cache',
        'payroll_fines',
        'payroll_rewards',
        'payroll_settings',
        'recovery_requests',
        'redemption_audit_logs',
        'rent_items',
        'rent_settings',
        'rent_waivers',
        'store_item_blocks',
        'store_items',
        'student_recovery_codes',
        'student_teachers',
        'students',
        'user_reports',
    ]

    for table_name in tables:
        _add_join_code(table_name)

    # 1) Backfill settings tables by explicit teacher_id + block -> teacher_blocks.join_code mapping.
    if table_exists('teacher_blocks'):
        for table_name in ['banking_settings', 'hall_pass_settings', 'payroll_settings', 'rent_settings']:
            if table_exists(table_name) and column_exists(table_name, 'teacher_id') and column_exists(table_name, 'block'):
                op.execute(
                    sa.text(
                        f"""
                        UPDATE {table_name}
                        SET join_code = (
                            SELECT tb.join_code
                            FROM teacher_blocks tb
                            WHERE tb.teacher_id = {table_name}.teacher_id
                              AND tb.block = {table_name}.block
                            LIMIT 1
                        )
                        WHERE join_code IS NULL
                          AND teacher_id IS NOT NULL
                          AND block IS NOT NULL
                        """
                    )
                )

    # 2) Backfill teacher-scoped tables only when a teacher owns exactly one join_code.
    if table_exists('teacher_blocks'):
        for table_name, teacher_col in [
            ('payroll_cache', 'teacher_id'),
            ('payroll_fines', 'teacher_id'),
            ('payroll_rewards', 'teacher_id'),
            ('store_items', 'teacher_id'),
            ('insurance_policies', 'teacher_id'),
            ('demo_students', 'admin_id'),
            ('recovery_requests', 'admin_id'),
            ('deletion_requests', 'admin_id'),
        ]:
            if table_exists(table_name) and column_exists(table_name, teacher_col):
                op.execute(
                    sa.text(
                        f"""
                        UPDATE {table_name}
                        SET join_code = (
                            SELECT MIN(tb.join_code)
                            FROM teacher_blocks tb
                            WHERE tb.teacher_id = {table_name}.{teacher_col}
                            GROUP BY tb.teacher_id
                            HAVING COUNT(DISTINCT tb.join_code) = 1
                        )
                        WHERE join_code IS NULL
                          AND {teacher_col} IS NOT NULL
                        """
                    )
                )

    # 3) Backfill from direct record lineage where possible.
    if table_exists('insurance_claims') and table_exists('student_insurance'):
        op.execute(
            sa.text(
                """
                UPDATE insurance_claims
                SET join_code = (
                    SELECT si.join_code
                    FROM student_insurance si
                    WHERE si.id = insurance_claims.student_insurance_id
                    LIMIT 1
                )
                WHERE join_code IS NULL
                """
            )
        )

    if table_exists('redemption_audit_logs') and table_exists('student_items'):
        op.execute(
            sa.text(
                """
                UPDATE redemption_audit_logs
                SET join_code = (
                    SELECT si.join_code
                    FROM student_items si
                    WHERE si.id = redemption_audit_logs.student_item_id
                    LIMIT 1
                )
                WHERE join_code IS NULL
                """
            )
        )

    if table_exists('issue_status_history') and table_exists('issues'):
        op.execute(
            sa.text(
                """
                UPDATE issue_status_history
                SET join_code = (
                    SELECT i.join_code
                    FROM issues i
                    WHERE i.id = issue_status_history.issue_id
                    LIMIT 1
                )
                WHERE join_code IS NULL
                """
            )
        )

    if table_exists('issue_resolution_actions') and table_exists('issues'):
        op.execute(
            sa.text(
                """
                UPDATE issue_resolution_actions
                SET join_code = (
                    SELECT i.join_code
                    FROM issues i
                    WHERE i.id = issue_resolution_actions.issue_id
                    LIMIT 1
                )
                WHERE join_code IS NULL
                """
            )
        )

    if table_exists('rent_items') and table_exists('rent_settings'):
        op.execute(
            sa.text(
                """
                UPDATE rent_items
                SET join_code = (
                    SELECT rs.join_code
                    FROM rent_settings rs
                    WHERE rs.id = rent_items.rent_setting_id
                    LIMIT 1
                )
                WHERE join_code IS NULL
                """
            )
        )

    if table_exists('store_item_blocks') and table_exists('store_items'):
        op.execute(
            sa.text(
                """
                UPDATE store_item_blocks
                SET join_code = (
                    SELECT si.join_code
                    FROM store_items si
                    WHERE si.id = store_item_blocks.store_item_id
                    LIMIT 1
                )
                WHERE join_code IS NULL
                """
            )
        )

    # Student-scoped lineage where student linkage is explicit.
    if table_exists('students') and table_exists('teacher_blocks'):
        op.execute(
            sa.text(
                """
                UPDATE students
                SET join_code = (
                    SELECT tb.join_code
                    FROM teacher_blocks tb
                    WHERE tb.student_id = students.id
                    ORDER BY tb.id ASC
                    LIMIT 1
                )
                WHERE join_code IS NULL
                """
            )
        )

    if table_exists('student_teachers') and table_exists('teacher_blocks'):
        op.execute(
            sa.text(
                """
                UPDATE student_teachers
                SET join_code = (
                    SELECT tb.join_code
                    FROM teacher_blocks tb
                    WHERE tb.student_id = student_teachers.student_id
                      AND tb.teacher_id = student_teachers.admin_id
                    ORDER BY tb.id ASC
                    LIMIT 1
                )
                WHERE join_code IS NULL
                """
            )
        )

    if table_exists('student_recovery_codes') and table_exists('students'):
        op.execute(
            sa.text(
                """
                UPDATE student_recovery_codes
                SET join_code = (
                    SELECT s.join_code
                    FROM students s
                    WHERE s.id = student_recovery_codes.student_id
                    LIMIT 1
                )
                WHERE join_code IS NULL
                """
            )
        )

    if table_exists('rent_waivers') and table_exists('students'):
        op.execute(
            sa.text(
                """
                UPDATE rent_waivers
                SET join_code = (
                    SELECT s.join_code
                    FROM students s
                    WHERE s.id = rent_waivers.student_id
                    LIMIT 1
                )
                WHERE join_code IS NULL
                """
            )
        )


def downgrade():
    tables = [
        'user_reports',
        'students',
        'student_teachers',
        'student_recovery_codes',
        'store_items',
        'store_item_blocks',
        'rent_waivers',
        'rent_settings',
        'rent_items',
        'redemption_audit_logs',
        'recovery_requests',
        'payroll_settings',
        'payroll_rewards',
        'payroll_fines',
        'payroll_cache',
        'jobs_settings',
        'job_templates',
        'job_applications',
        'issue_status_history',
        'issue_resolution_actions',
        'insurance_policy_blocks',
        'insurance_policies',
        'insurance_claims',
        'hall_pass_settings',
        'employee_job_warnings',
        'employee_job_assignments',
        'demo_students',
        'deletion_requests',
        'contract_job_claims',
        'banking_settings',
    ]

    for table_name in tables:
        _drop_join_code(table_name)
