# Migration Fix: 1a4ee2388d62 - Conditional Index Drops

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DB-005       | 1.0     | 2026-03-01     | N/A        | Normative                 |

## Problem

The migration `1a4ee2388d62_add_teacher_analytics.py` was failing with the error:

```
psycopg2.errors.UndefinedObject: index "ix_admin_credentials_credential_id" does not exist
```

## Root Cause

There were **two parallel migration chains** for creating the `admin_credentials` and `system_admin_credentials` tables:

### Chain 1: Without Index (newer path)
- `55f079e43ae6` → `ed9de5ef6f79` (creates tables without index) → `56612765d072`

### Chain 2: With Index (older path)  
- `64f0fdfc2079` (creates tables **with** index `ix_admin_credentials_credential_id`)

The migration `1a4ee2388d62` assumed the index existed and tried to drop it unconditionally, causing failures for databases that followed Chain 1.

## Solution

Modified `1a4ee2388d62_add_teacher_analytics.py` to **conditionally** drop indexes and columns only if they exist:

### Before (lines 97-103):
```python
with op.batch_alter_table('admin_credentials', schema=None) as batch_op:
    batch_op.drop_index(batch_op.f('ix_admin_credentials_credential_id'))
    batch_op.drop_column('public_key')
    batch_op.drop_column('aaguid')
    batch_op.drop_column('sign_count')
    batch_op.drop_column('transports')
```

### After (lines 97-115):
```python
# Conditionally drop index and columns from admin_credentials if they exist
# These may not exist depending on which migration path was taken
bind = op.get_bind()
inspector = sa.inspect(bind)

admin_cred_indexes = {idx['name'] for idx in inspector.get_indexes('admin_credentials')}
admin_cred_columns = {col['name'] for col in inspector.get_columns('admin_credentials')}

with op.batch_alter_table('admin_credentials', schema=None) as batch_op:
    if 'ix_admin_credentials_credential_id' in admin_cred_indexes:
        batch_op.drop_index(batch_op.f('ix_admin_credentials_credential_id'))
    if 'public_key' in admin_cred_columns:
        batch_op.drop_column('public_key')
    if 'aaguid' in admin_cred_columns:
        batch_op.drop_column('aaguid')
    if 'sign_count' in admin_cred_columns:
        batch_op.drop_column('sign_count')
    if 'transports' in admin_cred_columns:
        batch_op.drop_column('transports')
```

The same pattern was applied to `system_admin_credentials` (lines 252-266).

## Testing

Created comprehensive tests in `tests/test_migration_1a4ee2388d62_fix.py`:

1. **test_conditional_index_drop_logic** - Verifies index drop works when index exists
2. **test_conditional_index_drop_when_missing** - Verifies no error when index is missing
3. **test_column_existence_check** - Verifies column detection logic
4. **test_both_tables_pattern** - Tests both admin_credentials and system_admin_credentials scenarios

All tests pass ✓

## Impact

- ✅ Migration now works regardless of which migration path the database followed
- ✅ No breaking changes for databases that already have the index
- ✅ No errors for databases that don't have the index
- ✅ Idempotent - can be run multiple times safely

## Files Changed

1. `migrations/versions/1a4ee2388d62_add_teacher_analytics.py` - Fixed conditional drops
2. `tests/test_migration_1a4ee2388d62_fix.py` - Added comprehensive tests

## Related Migrations

- `64f0fdfc2079_add_admin_credential_table_for_teacher_.py` - Created tables with index
- `ed9de5ef6f79_create_passkey_credential_tables_v2.py` - Created tables without index
- `56612765d072_update_passkey_credential_table.py` - Modified tables (no index operations)
