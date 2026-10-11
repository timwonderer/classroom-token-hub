"""Make obligation ASSESSMENT replay-safe under concurrent reconcile runs.

Revision ID: 6a01dc7a606b
Revises: 35a9a0d3ab93
Create Date: 2026-10-10 23:50:00.000000

FEAT-OBL-001 §IV.3 requires assessment to be replay-safe by
(internal_ref, correlation_id). ``check_idempotency_assessment`` performs
exactly that check, but only as a read before the insert, with no lock and
no database constraint behind it: 8a7b6c5d4e3f (2026-07-25) intentionally
dropped the *unique* index on ``correlation_id`` alone, because one
correlation_id legitimately carries several ``event_type`` rows (ASSESSMENT,
PAYMENT, WAIVED, WITHDRAWN) for the same obligation. That migration's own
message says so explicitly. It left nothing in its place scoped to the
narrower tuple FEAT-OBLI-001 actually promises, so two reconcile runs that
overlap (the scheduler losing and regaining its ownership lock without the
old run having finished — see app/scheduler_ownership.py and audit O5) can
both pass the read-then-insert check before either commits, and both insert
an ASSESSMENT row for the same (internal_ref, correlation_id).

This adds a unique constraint scoped to (internal_ref, correlation_id,
event_type). It protects exactly the replay-safety contract FEAT-OBLI-001
claims — one ASSESSMENT per lineage/liability — without reintroducing the
single-column uniqueness 8a7b6c5d4e3f correctly removed: a PAYMENT or WAIVED
row sharing the same correlation_id is a different event_type and is
unaffected.

Operational note before deploying: if this constraint is ever violated by
existing rows (a duplicate ASSESSMENT already written under the race this
closes), the ADD CONSTRAINT step fails loudly rather than silently
succeeding. Check for duplicates before running this against a database that
has been live under the unguarded window:

    SELECT internal_ref, correlation_id, event_type, count(*)
    FROM assessment_events
    WHERE event_type = 'ASSESSMENT'
    GROUP BY internal_ref, correlation_id, event_type
    HAVING count(*) > 1;

A non-empty result needs a decision (which duplicate is canonical) before
this migration can apply; that decision is outside the scope of a migration
and is not made here.
"""
from alembic import op
import sqlalchemy as sa


revision = '6a01dc7a606b'
down_revision = '35a9a0d3ab93'
branch_labels = None
depends_on = None

CONSTRAINT_NAME = 'uq_assessment_events_internal_ref_correlation_event_type'


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def unique_constraint_exists(table_name, constraint_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        names = [c['name'] for c in inspector.get_unique_constraints(table_name)]
        return constraint_name in names
    except Exception:
        return False


def upgrade():
    if not table_exists('assessment_events'):
        return
    if not unique_constraint_exists('assessment_events', CONSTRAINT_NAME):
        op.create_unique_constraint(
            CONSTRAINT_NAME,
            'assessment_events',
            ['internal_ref', 'correlation_id', 'event_type'],
        )
        print(f"✅ Added unique constraint {CONSTRAINT_NAME} on assessment_events")
    else:
        print(f"⚠️  Constraint {CONSTRAINT_NAME} already exists on assessment_events, skipping...")


def downgrade():
    if not table_exists('assessment_events'):
        return
    if unique_constraint_exists('assessment_events', CONSTRAINT_NAME):
        op.drop_constraint(CONSTRAINT_NAME, 'assessment_events', type_='unique')
        print(f"❌ Dropped unique constraint {CONSTRAINT_NAME} from assessment_events")
    else:
        print(f"⚠️  Constraint {CONSTRAINT_NAME} does not exist on assessment_events, skipping...")
