"""Terminal PROD eligibility receipts with immutable creation lineage.

DOM-PROD-001 XI.4, DOM-OPS-002 6.1, FEAT-PROD-005. No history backfill.
"""
from alembic import op
import sqlalchemy as sa

revision = 'f9a3c7d1e620'
down_revision = 'f8b2d6e0a410'
branch_labels = None
depends_on = None

def table_exists(table_name):
    return sa.inspect(op.get_bind()).has_table(table_name)


def column_exists(table_name, column_name):
    return any(c['name'] == column_name for c in sa.inspect(op.get_bind()).get_columns(table_name))


def index_exists(table_name, index_name):
    return any(i['name'] == index_name for i in sa.inspect(op.get_bind()).get_indexes(table_name))


def check_constraint_exists(table_name, constraint_name):
    return any(c['name'] == constraint_name for c in sa.inspect(op.get_bind()).get_check_constraints(table_name))



def upgrade():
    if not table_exists('attendance_interval_invalidation'):
        op.create_table('attendance_interval_invalidation',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False),
            sa.Column('target_seat_id', sa.Integer(), sa.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False),
            sa.Column('actor_seat_id', sa.Integer(), nullable=False),
            sa.Column('opening_event_id', sa.Integer(), sa.ForeignKey('attendance_sessions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('closing_event_id', sa.Integer(), sa.ForeignKey('attendance_sessions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('reason_code', sa.String(32), nullable=False),
            sa.Column('idempotency_key', sa.String(128), nullable=False),
            sa.Column('correlation_id', sa.String(100), nullable=False),
            sa.Column('receipt_json', sa.JSON(), nullable=False),
            sa.Column('lineage_event_id', sa.Integer(), nullable=True),
            sa.Column('lineage_token', sa.String(64), nullable=True),
            sa.Column('lineage_version', sa.Integer(), nullable=True),
            sa.UniqueConstraint('class_id', 'target_seat_id', 'opening_event_id', 'closing_event_id', name='uq_attendance_invalidation_interval'),
            sa.UniqueConstraint('class_id', 'idempotency_key', name='uq_attendance_invalidation_command'),
            sa.CheckConstraint("reason_code IN ('INVALID_ATTENDANCE','NON_WORK_ACTIVITY','DUPLICATE_PARTICIPATION')", name='ck_attendance_invalidation_reason'))
    for field in ('class_id', 'target_seat_id', 'actor_seat_id'):
        if not index_exists('attendance_interval_invalidation', 'ix_attendance_interval_invalidation_'+field):
            op.create_index('ix_attendance_interval_invalidation_'+field, 'attendance_interval_invalidation', [field])
    op.execute("""
    CREATE OR REPLACE FUNCTION guard_attendance_invalidation_insert() RETURNS trigger AS $$
    BEGIN
      IF NEW.lineage_event_id IS NOT NULL OR NEW.lineage_token IS NOT NULL OR NEW.lineage_version IS NOT NULL THEN
        RAISE EXCEPTION 'Invalidation lineage initializes after INSERT only';
      END IF;
      IF NOT EXISTS (SELECT 1 FROM seats a WHERE a.id=NEW.actor_seat_id AND a.class_id=NEW.class_id AND a.role='teacher')
        OR NOT EXISTS (SELECT 1 FROM seats t WHERE t.id=NEW.target_seat_id AND t.class_id=NEW.class_id AND t.role='student')
        OR NOT EXISTS (SELECT 1 FROM attendance_sessions a JOIN attendance_sessions b ON b.id=NEW.closing_event_id
          WHERE a.id=NEW.opening_event_id AND a.class_id=NEW.class_id AND b.class_id=NEW.class_id
            AND a.target_seat_id=NEW.target_seat_id AND b.target_seat_id=NEW.target_seat_id
            AND a.status='active' AND b.status='inactive' AND b.timestamp>=a.timestamp) THEN
        RAISE EXCEPTION 'Invalidation source and seats must share canonical class/target scope';
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    DROP TRIGGER IF EXISTS attendance_invalidation_insert_guard ON attendance_interval_invalidation; CREATE TRIGGER attendance_invalidation_insert_guard BEFORE INSERT ON attendance_interval_invalidation
      FOR EACH ROW EXECUTE FUNCTION guard_attendance_invalidation_insert();
    CREATE OR REPLACE FUNCTION guard_attendance_invalidation_update() RETURNS trigger AS $$
    BEGIN
      IF NOT payroll_creator_is_uncommitted(OLD.xmin) OR OLD.lineage_event_id IS NOT NULL
        OR OLD.lineage_token IS NOT NULL OR OLD.lineage_version IS NOT NULL
        OR NEW.lineage_event_id IS NULL OR NEW.lineage_token IS NULL OR NEW.lineage_version IS NULL
        OR NEW.receipt_json::text IS DISTINCT FROM OLD.receipt_json::text
        OR (to_jsonb(NEW)-ARRAY['lineage_event_id','lineage_token','lineage_version']) IS DISTINCT FROM
           (to_jsonb(OLD)-ARRAY['lineage_event_id','lineage_token','lineage_version']) THEN
        RAISE EXCEPTION 'Attendance invalidation is immutable; lineage initializes once in creating transaction only';
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    DROP TRIGGER IF EXISTS attendance_invalidation_update_guard ON attendance_interval_invalidation; CREATE TRIGGER attendance_invalidation_update_guard BEFORE UPDATE ON attendance_interval_invalidation
      FOR EACH ROW EXECUTE FUNCTION guard_attendance_invalidation_update();
    CREATE OR REPLACE FUNCTION guard_attendance_invalidation_delete() RETURNS trigger AS $$
    BEGIN
      IF COALESCE(current_setting('cth.class_universe_destroying',true),'')='on'
        OR NOT EXISTS (SELECT 1 FROM seats WHERE id=OLD.target_seat_id) THEN RETURN OLD; END IF;
      RAISE EXCEPTION 'Attendance invalidation belongs to surviving target; lifecycle destruction only';
    END; $$ LANGUAGE plpgsql;
    DROP TRIGGER IF EXISTS attendance_invalidation_delete_guard ON attendance_interval_invalidation; CREATE TRIGGER attendance_invalidation_delete_guard BEFORE DELETE ON attendance_interval_invalidation
      FOR EACH ROW EXECUTE FUNCTION guard_attendance_invalidation_delete();
    CREATE OR REPLACE FUNCTION require_attendance_invalidation_lineage() RETURNS trigger AS $$
    DECLARE final_row attendance_interval_invalidation%ROWTYPE;
    BEGIN
      SELECT * INTO final_row FROM attendance_interval_invalidation WHERE id=NEW.id;
      IF NOT FOUND THEN RETURN NULL; END IF;
      IF final_row.lineage_event_id IS NULL OR final_row.lineage_token IS NULL OR final_row.lineage_version IS NULL
        OR NOT EXISTS (SELECT 1 FROM audit_events a WHERE a.id=final_row.lineage_event_id
          AND payroll_creator_is_uncommitted(a.xmin) AND a.table_name='attendance_interval_invalidation'
          AND a.row_pk=final_row.id::text AND a.class_id=final_row.class_id AND a.chain_scope='class:'||final_row.class_id
          AND a.operation='INSERT' AND a.feat_id='FEAT-PROD-005'
          AND a.hmac_signature=final_row.lineage_token AND a.signature_version=final_row.lineage_version) THEN
        RAISE EXCEPTION 'New attendance invalidation requires matching creation lineage before commit';
      END IF;
      RETURN NULL;
    END; $$ LANGUAGE plpgsql;
    DROP TRIGGER IF EXISTS attendance_invalidation_lineage_required ON attendance_interval_invalidation; CREATE CONSTRAINT TRIGGER attendance_invalidation_lineage_required AFTER INSERT ON attendance_interval_invalidation
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION require_attendance_invalidation_lineage();
    """)


def downgrade():
    raise RuntimeError('Terminal invalidation evidence cannot be removed by downgrade; reviewed forward migration required.')
