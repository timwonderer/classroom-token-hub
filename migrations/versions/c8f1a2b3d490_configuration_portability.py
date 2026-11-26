"""Configuration capability, temporary receipts and canonical insurance groups.

Revision ID: c8f1a2b3d490
Revises: a4d7e9c2f1b6
Authority: DOM-CLASS-001, DOM-POL-001A, SPEC-CLASS-001 (2026-10-25).
Forward-only: successor publication preserves historical definition payloads.
"""
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision = 'c8f1a2b3d490'
down_revision = 'a4d7e9c2f1b6'
branch_labels = None
depends_on = None


def table_exists(table_name):
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def column_exists(table_name, column_name):
    return column_name in [c['name'] for c in sa.inspect(op.get_bind()).get_columns(table_name)]


def index_exists(table_name, index_name):
    return index_name in [i['name'] for i in sa.inspect(op.get_bind()).get_indexes(table_name)]


def foreign_key_exists(table_name, fk_name):
    return fk_name in [f['name'] for f in sa.inspect(op.get_bind()).get_foreign_keys(table_name)]


def upgrade():
    for name, typ in [('configuration_export_verifier', sa.String(64)), ('configuration_export_expires_at', sa.DateTime(timezone=True))]:
        if not column_exists('users', name):
            op.add_column('users', sa.Column(name, typ, nullable=True))
    if not table_exists('configuration_import_receipts'):
        op.create_table('configuration_import_receipts',
            sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.class_id', ondelete='CASCADE'), primary_key=True),
            sa.Column('operation_id', sa.String(36), primary_key=True),
            sa.Column('actor_seat_id', sa.Integer(), sa.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False),
            sa.Column('fingerprint', sa.String(64), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('result', sa.JSON(), nullable=False))
    if not index_exists('configuration_import_receipts', 'ix_configuration_import_receipts_expires_at'):
        op.create_index('ix_configuration_import_receipts_expires_at', 'configuration_import_receipts', ['expires_at'])
    if not table_exists('insurance_tier_groups'):
        op.create_table('insurance_tier_groups',
            sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.class_id', ondelete='CASCADE'), primary_key=True),
            sa.Column('group_id', sa.String(36), primary_key=True),
            sa.Column('name', sa.String(60), nullable=False))
    if not column_exists('insurance_policies', 'tier_group_id'):
        op.add_column('insurance_policies', sa.Column('tier_group_id', sa.String(36), nullable=True))
    if not foreign_key_exists('insurance_policies', 'fk_insurance_policy_group'):
        op.create_foreign_key('fk_insurance_policy_group', 'insurance_policies', 'insurance_tier_groups', ['class_id','tier_group_id'], ['class_id','group_id'])

    conn = op.get_bind()
    # Serialize the cutover against authoring and renewal; never run on production
    # without the normal approved migration/write-stop release procedure.
    conn.execute(sa.text('LOCK TABLE insurance_policies IN ACCESS EXCLUSIVE MODE'))
    meta = sa.MetaData()
    policies = sa.Table('insurance_policies', meta, autoload_with=conn)
    groups = sa.Table('insurance_tier_groups', meta, autoload_with=conn)
    rows = [dict(r) for r in conn.execute(sa.select(policies)).mappings()]
    by_id = {r['policy_uuid']: r for r in rows}
    successors = {}
    for r in sorted(rows, key=lambda r: (r['created_at'], r['policy_uuid'])):
        if r['supersedes_policy_uuid']:
            successors[(r['class_id'], r['supersedes_policy_uuid'])] = r
    # An existing live grouped grant must resolve by explicit links to a definition
    # receiving a canonical successor. Never infer a historical relationship.
    grants = conn.execute(sa.text("""SELECT e.class_id, e.payload->>'policy_uuid' AS policy_uuid
        FROM entitlement_events e WHERE e.entitlement_type='INSURANCE' AND e.event_type='GRANTED'
        AND NOT EXISTS (SELECT 1 FROM entitlement_events t WHERE t.class_id=e.class_id
        AND t.entitlement_id=e.entitlement_id AND t.event_type IN ('EXPIRED','REVOKED'))""")).mappings()
    for grant in grants:
        r = by_id.get(grant['policy_uuid'])
        if not r or r['class_id'] != grant['class_id']:
            raise RuntimeError('Insurance migration: live coverage has unavailable policy evidence')
        seen = set()
        while (r['class_id'], r['policy_uuid']) in successors:
            if r['policy_uuid'] in seen:
                raise RuntimeError('Insurance migration: cyclic successor evidence')
            seen.add(r['policy_uuid']);r = successors[(r['class_id'], r['policy_uuid'])]
        if r['tier_group'] and not r['tier_group_id'] and r['availability_state'] not in ('IN_USE', 'HIDDEN'):
            raise RuntimeError('Insurance migration: live grouped coverage lacks an explicit successor path')

    # Replace the label-keyed index before publication. New identity backstop is
    # installed in this same transaction, before application writes can resume.
    index = 'uq_insurance_policies_group_rank_in_use'
    if index_exists('insurance_policies', index):
        op.drop_index(index, table_name='insurance_policies')
    identities = {}
    now = conn.execute(sa.text('SELECT CURRENT_TIMESTAMP')).scalar_one()
    for old in rows:
        if old['tier_group_id'] or not old['tier_group'] or old['availability_state'] not in ('IN_USE','HIDDEN'):
            continue
        if old['tier_level'] not in (1, 2, 3):
            raise RuntimeError('Insurance migration: grouped policy has an invalid rank')
        # Explicit one-time interpretation of the former contract, never a runtime fallback.
        key = (old['class_id'], old['tier_group'])
        if key not in identities:
            gid = str(uuid4());identities[key] = gid
            conn.execute(groups.insert().values(class_id=key[0], group_id=gid, name=key[1]))
        new = dict(old)
        new.update(policy_uuid=str(uuid4()), tier_group_id=identities[key], supersedes_policy_uuid=old['policy_uuid'], created_at=now, retired_at=None)
        conn.execute(policies.update().where(policies.c.policy_uuid==old['policy_uuid']).values(availability_state='RETIRED', retired_at=now))
        conn.execute(policies.insert().values(**new))
    if not index_exists('insurance_policies', index):
        op.create_index(index, 'insurance_policies', ['class_id','tier_group_id','tier_level'], unique=True,
            postgresql_where=sa.text("availability_state = 'IN_USE' AND tier_group_id IS NOT NULL"))


def downgrade():
    raise RuntimeError('Forward-only insurance succession: restore an approved snapshot or fix forward')
