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

This adds a **partial** unique index scoped to (internal_ref, correlation_id)
WHERE event_type = 'ASSESSMENT'. A plain (unfiltered) unique constraint on
(internal_ref, correlation_id, event_type) was tried first and is wrong:
satisfy_obligation_feat.py's own docstring says "PAYMENT may occur multiple
times for partial payment" — "one obligation → one correlation → many
PAYMENT events" — all sharing the assessment's internal_ref and
correlation_id with event_type='PAYMENT'. A full-column constraint would
make the *second* partial payment for the same obligation an IntegrityError,
which is exactly the kind of outage this migration exists to prevent, not
cause. Filtering the index to event_type = 'ASSESSMENT' protects only the
tuple FEAT-OBLI-001 actually promises to be unique — "one ASSESSMENT per
lineage/liability" — and leaves PAYMENT/WAIVED/WITHDRAWN rows, including
repeated PAYMENTs, completely unaffected regardless of how many share a
correlation_id.

Operational note before deploying: if this index is ever violated by
existing rows (a duplicate ASSESSMENT already written under the race this
closes), the CREATE UNIQUE INDEX step fails loudly rather than silently
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

INDEX_NAME = 'uq_assessment_events_assessment_internal_ref_correlation'


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        names = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in names
    except Exception:
        return False


def upgrade():
    if not table_exists('assessment_events'):
        return
    # A partial unique index, not a table-wide unique constraint: it only
    # enforces uniqueness among rows where event_type = 'ASSESSMENT'.
    # PAYMENT, WAIVED and WITHDRAWN rows — including multiple PAYMENT rows
    # for the same obligation (partial payments) — are invisible to it and
    # can repeat (internal_ref, correlation_id) freely.
    if not index_exists('assessment_events', INDEX_NAME):
        op.create_index(
            INDEX_NAME,
            'assessment_events',
            ['internal_ref', 'correlation_id'],
            unique=True,
            postgresql_where=sa.text("event_type = 'ASSESSMENT'"),
        )
        print(f"✅ Added partial unique index {INDEX_NAME} on assessment_events (event_type = 'ASSESSMENT')")
    else:
        print(f"⚠️  Index {INDEX_NAME} already exists on assessment_events, skipping...")


def downgrade():
    if not table_exists('assessment_events'):
        return
    if index_exists('assessment_events', INDEX_NAME):
        op.drop_index(INDEX_NAME, table_name='assessment_events')
        print(f"❌ Dropped partial unique index {INDEX_NAME} from assessment_events")
    else:
        print(f"⚠️  Index {INDEX_NAME} does not exist on assessment_events, skipping...")
