"""Enforce student must have teacher link

Revision ID: 1adc6456ab0e
Revises: b9c0d1e2f3a4
Create Date: 2026-03-09 02:59:59.285956

"""
from alembic import op
import sqlalchemy as sa


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False

def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False

def get_foreign_keys_by_column(table_name, column_name):
    """
    Get foreign key constraints that reference a specific column.
    
    Use this instead of hardcoding FK names in downgrade.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []


def function_exists(function_name):
    """Check if a PostgreSQL function exists in the public schema."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE p.proname = :function_name
              AND n.nspname = 'public'
            LIMIT 1
            """
        ),
        {"function_name": function_name},
    ).scalar()
    return bool(result)


def constraint_trigger_exists(trigger_name, table_name):
    """Check if a trigger exists on a specific table."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE t.tgname = :trigger_name
              AND c.relname = :table_name
              AND n.nspname = 'public'
              AND NOT t.tgisinternal
            LIMIT 1
            """
        ),
        {"trigger_name": trigger_name, "table_name": table_name},
    ).scalar()
    return bool(result)

# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

# revision identifiers, used by Alembic.
revision = '1adc6456ab0e'
down_revision = 'b9c0d1e2f3a4'
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists('students') or not table_exists('student_teachers'):
        print("⚠️  Required tables missing (students/student_teachers), skipping...")
        return

    if not function_exists('enforce_student_has_teacher_link'):
        op.execute(
            sa.text(
                """
                CREATE FUNCTION public.enforce_student_has_teacher_link()
                RETURNS trigger
                LANGUAGE plpgsql
                AS $$
                DECLARE
                    sid INTEGER;
                BEGIN
                    IF TG_TABLE_NAME = 'students' THEN
                        IF TG_OP = 'DELETE' THEN
                            RETURN NULL;
                        END IF;
                        sid := NEW.id;
                    ELSIF TG_TABLE_NAME = 'student_teachers' THEN
                        IF TG_OP = 'DELETE' THEN
                            sid := OLD.student_id;
                        ELSE
                            IF TG_OP = 'UPDATE' AND OLD.student_id IS DISTINCT FROM NEW.student_id THEN
                                IF EXISTS (SELECT 1 FROM students WHERE id = OLD.student_id)
                                   AND NOT EXISTS (SELECT 1 FROM student_teachers WHERE student_id = OLD.student_id)
                                THEN
                                    RAISE EXCEPTION
                                        'Invariant violation: students.id=% has no student_teachers link after update',
                                        OLD.student_id;
                                END IF;
                            END IF;
                            sid := NEW.student_id;
                        END IF;
                    ELSE
                        RETURN NULL;
                    END IF;

                    IF sid IS NULL THEN
                        RETURN NULL;
                    END IF;

                    IF EXISTS (SELECT 1 FROM students WHERE id = sid)
                       AND NOT EXISTS (SELECT 1 FROM student_teachers WHERE student_id = sid)
                    THEN
                        RAISE EXCEPTION
                            'Invariant violation: students.id=% must have at least one student_teachers link',
                            sid;
                    END IF;

                    RETURN NULL;
                END;
                $$;
                """
            )
        )
        print("✅ Created function enforce_student_has_teacher_link")
    else:
        print("⚠️  Function enforce_student_has_teacher_link already exists, skipping...")

    if not constraint_trigger_exists('ct_students_require_teacher_link', 'students'):
        op.execute(
            sa.text(
                """
                CREATE CONSTRAINT TRIGGER ct_students_require_teacher_link
                AFTER INSERT OR UPDATE
                ON public.students
                DEFERRABLE INITIALLY DEFERRED
                FOR EACH ROW
                EXECUTE FUNCTION public.enforce_student_has_teacher_link();
                """
            )
        )
        print("✅ Created constraint trigger ct_students_require_teacher_link")
    else:
        print("⚠️  Trigger ct_students_require_teacher_link already exists, skipping...")

    if not constraint_trigger_exists('ct_student_teachers_require_student_link', 'student_teachers'):
        op.execute(
            sa.text(
                """
                CREATE CONSTRAINT TRIGGER ct_student_teachers_require_student_link
                AFTER INSERT OR UPDATE OR DELETE
                ON public.student_teachers
                DEFERRABLE INITIALLY DEFERRED
                FOR EACH ROW
                EXECUTE FUNCTION public.enforce_student_has_teacher_link();
                """
            )
        )
        print("✅ Created constraint trigger ct_student_teachers_require_student_link")
    else:
        print("⚠️  Trigger ct_student_teachers_require_student_link already exists, skipping...")


def downgrade():
    if constraint_trigger_exists('ct_student_teachers_require_student_link', 'student_teachers'):
        op.execute(sa.text("DROP TRIGGER ct_student_teachers_require_student_link ON public.student_teachers;"))
        print("❌ Dropped trigger ct_student_teachers_require_student_link")
    else:
        print("⚠️  Trigger ct_student_teachers_require_student_link not found, skipping...")

    if constraint_trigger_exists('ct_students_require_teacher_link', 'students'):
        op.execute(sa.text("DROP TRIGGER ct_students_require_teacher_link ON public.students;"))
        print("❌ Dropped trigger ct_students_require_teacher_link")
    else:
        print("⚠️  Trigger ct_students_require_teacher_link not found, skipping...")

    if function_exists('enforce_student_has_teacher_link'):
        op.execute(sa.text("DROP FUNCTION public.enforce_student_has_teacher_link();"))
        print("❌ Dropped function enforce_student_has_teacher_link")
    else:
        print("⚠️  Function enforce_student_has_teacher_link not found, skipping...")
