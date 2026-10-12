"""A hall pass is spent at most once: unique hall_pass_logs.hall_pass_id.

Owner ruling 2026-10-09: the hall-pass log is the only legal consumption
reference (FEAT-PROD-002 §III), and using a pass writes no entitlement event
(DOM-STORE-001 §VIII.E.6). The Store's one-terminal-event-per-lineage index used
to stop a second use of the same pass; with no CONSUMED event that protection
moves here. A partial unique index on hall_pass_id (the pass's entitlement_id)
lets each pass be logged at most once; logs for non-consuming destinations
carry no hall_pass_id and are unaffected.

EXPAND only: no column or data changes. The upgrade refuses, changing nothing,
if any pass is already logged twice. Production on 2026-10-09 had 17 logs on 17
distinct passes.
"""
from alembic import op
import sqlalchemy as sa

revision = '35a9a0d3ab93'
down_revision = 'f9a3c7d1e620'
branch_labels = None
depends_on = None

INDEX_NAME = 'uq_hall_pass_logs_hall_pass_id'


def table_exists(table_name):
    return sa.inspect(op.get_bind()).has_table(table_name)


def index_exists(table_name, index_name):
    return any(i['name'] == index_name for i in sa.inspect(op.get_bind()).get_indexes(table_name))


def _passes_logged_twice():
    return op.get_bind().execute(sa.text(
        "SELECT count(*) FROM (SELECT hall_pass_id FROM hall_pass_logs "
        "WHERE hall_pass_id IS NOT NULL GROUP BY hall_pass_id HAVING count(*) > 1) d"
    )).scalar()


def upgrade():
    if not table_exists('hall_pass_logs'):
        print("⚠️  Table hall_pass_logs does not exist, skipping...")
        return
    duplicates = _passes_logged_twice()
    if duplicates and not index_exists('hall_pass_logs', 'uq_hall_pass_logs_hall_pass_id'):
        raise RuntimeError(
            f"Refusing to add {INDEX_NAME}: {duplicates} hall pass(es) are logged more than "
            "once. Nothing was changed; resolve them before upgrading."
        )
    if not index_exists('hall_pass_logs', 'uq_hall_pass_logs_hall_pass_id'):
        op.create_index(
            'uq_hall_pass_logs_hall_pass_id',
            'hall_pass_logs',
            ['hall_pass_id'],
            unique=True,
            postgresql_where=sa.text('hall_pass_id IS NOT NULL'),
        )
        print(f"✅ Created {INDEX_NAME}")
    else:
        print(f"⚠️  Index {INDEX_NAME} already exists, skipping...")


def downgrade():
    if table_exists('hall_pass_logs') and index_exists('hall_pass_logs', 'uq_hall_pass_logs_hall_pass_id'):
        op.drop_index('uq_hall_pass_logs_hall_pass_id', table_name='hall_pass_logs')
        print(f"❌ Dropped {INDEX_NAME}")
    else:
        print(f"⚠️  Index {INDEX_NAME} does not exist, skipping...")
