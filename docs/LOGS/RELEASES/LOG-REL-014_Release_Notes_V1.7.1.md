# Release Notes - Version 1.7.1

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| LOG-REL-014      | 1.0     | 2026-03-01     | N/A        | Informative                |

**Release Date**: January 22, 2026
**Focus**: Critical Financial Precision Updates, Payroll Stability, and Documentation Hygiene

---

## Highlights

- **Decimal Precision Refactor** - Eliminated floating-point errors in all financial calculations by moving to strict `Decimal` arithmetic
- **Payroll Stability** - Fixed multitenancy leaks and JSON serialization crashes in payroll
- **Dashboard Integrity** - Resolved 500 errors caused by null transaction amounts
- **Documentation Hygiene** - Cleaned up repository structure and enforced clear separation of audience documentation

---

## Bug Fixes

### CRITICAL: Financial Precision
Refactored all financial logic to use Python's `Decimal` type throughout, not just for database storage.

**Fixed Issues**:

- Floating-point rounding errors causing "unpayable" residual balances (e.g., $0.0000001)
- Phantom overdraft fees triggered by -0.00 balances
- Interest calculation type errors mixing float and Decimal

**Changes**:

- Updated all balance calculation methods to return Decimal
- Refactored interest, rent, and payroll calculations to use Decimal arithmetic
- Added near-zero balance normalization (|balance| < $0.01 → $0.00)

### Payroll System
- **Multitenancy Fix**: Fixed payroll calculations leaking data across class periods (#664, #883)
- **Serialization Fix**: Fixed `TypeError` when serializing Decimal values for AJAX responses

### Student Dashboard
- **Null Handling**: Fixed crash loops when calculating weekly/monthly analytics with NULL transaction amounts (affected earnings/spending charts)
- **Performance**: Optimized recent deposits query to handle corrupted legacy data gracefully

### Miscellaneous
- **Duplicate Claims**: Added integrity checks for duplicate student account claims
- **Hall Pass Queue**: Fixed scoping issues for multi-teacher environments
- **Rent Display**: Corrected student courts and billing period labels in rent overview

---

## Documentation & Repository Organization

### Hygiene Updates
- **Canonical Locations**: Enforced single source of truth for all documentation files
- **Audience Separation**: Moved internal development docs to `docs/development/` and user guides to `docs/user-guides/`
- **Cleanup**: Archived obsolete reports and duplicate files to `docs/archive/`

---

## Upgrade Notes

### For Existing Deployments

1. **Pull latest code**:
   ```bash
   git pull origin main
   ```

2. **Run database migrations (None for this patch)**:
   ```bash
   flask db upgrade
   ```
   *Note: No new migrations in this patch release, but good practice to run.*

3. **Restart application**:
   ```bash
   sudo systemctl restart classroom-token-hub
   ```

### Breaking Changes
None. This release is fully backward compatible.

---

## Testing

All fixes have been verified with:

- New regression tests for Decimal/float type mixing
- Enhanced multitenancy test suite for payroll
- Manual verification of dashboard calculations

---

## What's Next

See [DEVELOPMENT.md](../../../DEVELOPMENT.md) for the active roadmap.

---

**Last Updated**: 2026-01-22
**Release Status**: Released
