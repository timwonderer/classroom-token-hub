import re

migration_file = "migrations/versions/e0babef88934_remove_legacy_scope_columns_from_.py"
with open(migration_file, 'r') as f:
    content = f.read()

upgrade_code = """def upgrade():
    op.execute("DROP POLICY IF EXISTS hall_pass_settings_tenant_isolation_select ON hall_pass_settings")
    op.execute("DROP POLICY IF EXISTS hall_pass_settings_tenant_isolation_insert ON hall_pass_settings")
    op.execute("DROP POLICY IF EXISTS hall_pass_settings_tenant_isolation_update ON hall_pass_settings")
    op.execute("DROP POLICY IF EXISTS hall_pass_settings_tenant_isolation_delete ON hall_pass_settings")

    if index_exists('hall_pass_settings', 'ix_hall_pass_settings_join_code'):
        op.drop_index(op.f('ix_hall_pass_settings_join_code'), table_name='hall_pass_settings')
    if index_exists('hall_pass_settings', 'ix_hall_pass_settings_teacher_id'):
        op.drop_index(op.f('ix_hall_pass_settings_teacher_id'), table_name='hall_pass_settings')
    
    fks = get_foreign_keys_by_column('hall_pass_settings', 'teacher_id')
    for fk in fks:
        op.drop_constraint(fk['name'], 'hall_pass_settings', type_='foreignkey')

    if column_exists('hall_pass_settings', 'block'):
        op.drop_column('hall_pass_settings', 'block')
    if column_exists('hall_pass_settings', 'join_code'):
        op.drop_column('hall_pass_settings', 'join_code')
    if column_exists('hall_pass_settings', 'teacher_id'):
        op.drop_column('hall_pass_settings', 'teacher_id')
"""

downgrade_code = """def downgrade():
    if not column_exists('hall_pass_settings', 'teacher_id'):
        op.add_column('hall_pass_settings', sa.Column('teacher_id', sa.INTEGER(), autoincrement=False, nullable=True))
    if not column_exists('hall_pass_settings', 'join_code'):
        op.add_column('hall_pass_settings', sa.Column('join_code', sa.VARCHAR(length=20), autoincrement=False, nullable=True))
    if not column_exists('hall_pass_settings', 'block'):
        op.add_column('hall_pass_settings', sa.Column('block', sa.VARCHAR(length=10), autoincrement=False, nullable=True))
    
    if not index_exists('hall_pass_settings', 'ix_hall_pass_settings_teacher_id'):
        op.create_index(op.f('ix_hall_pass_settings_teacher_id'), 'hall_pass_settings', ['teacher_id'], unique=False)
    if not index_exists('hall_pass_settings', 'ix_hall_pass_settings_join_code'):
        op.create_index(op.f('ix_hall_pass_settings_join_code'), 'hall_pass_settings', ['join_code'], unique=False)
"""

content = re.sub(r'def upgrade\(\):.*?(?=def downgrade\(\):)', upgrade_code + '\n\n', content, flags=re.DOTALL)
content = re.sub(r'def downgrade\(\):.*', downgrade_code, content, flags=re.DOTALL)

with open(migration_file, 'w') as f:
    f.write(content)
