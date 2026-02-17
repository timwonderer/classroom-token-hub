# Release Notes - Version 1.8.0

**Release Date**: February 8, 2026
**Focus**: Rent item types, coverage-period tracking, and stability/security fixes

---

## Highlights

- **Rent Item Types** - Added privilege, per-use, and hall pass rent item types with store integration and usage tracking
- **Coverage Period Tracking** - Rent payments now record the period they cover, removing month-boundary edge cases
- **Operational Fixes** - Insurance class scoping and rent purchase checks now respect the selected class period
- **Security Hardening** - Grafana proxy filtering tightened to prevent XSS

---

## Added

### Rent Item Types (Privilege / Per-Use / Hall Pass)
- New rent item types with distinct behavior for roster badges, store perks, and hall pass top-offs
- Store integration adds rent-perk badges and prevents accidental deletion of linked store items
- Per-use items grant free uses with `uses_remaining` tracking and "free use" redemption flow
- Mid-period edit guardrails prevent structural changes once rent has been paid for the current period

### Pre-Paid Rent Coverage Period Tracking
- Rent payments now store `coverage_month` and `coverage_year`
- Rent checks and purchase gating use coverage-based lookups (not wall-clock month/year)
- Itemized rent purchases now align to the same coverage period logic

---

## Fixed

- **Privilege badges** now only show privilege-type rent items (not per-use or hall pass items)
- **Insurance class selector** now scopes policies, enrollments, and claims to the selected class period
- **Rent purchase blocking** no longer fails when the due date crosses month boundaries
- **Issue ticket filing** no longer fails on Decimal JSON serialization
- **Duplicate store items** no longer created when applying rent settings to multiple blocks

---

## Changed

- **Redundant check removal** in `_add_period` helper to simplify logic in `app/routes/api.py`

---

## Security

- **Grafana proxy XSS protection** improved with case-insensitive MIME checks and SVG/XSL blocking
- **Duplicate `_is_safe_url` removal** to prevent shadowed definitions in student routes

---

## Upgrade Notes

### For Existing Deployments

1. **Pull latest code**:
   ```bash
   git pull origin main
   ```

2. **Run database migrations**:
   ```bash
   flask db upgrade
   ```
   **New migrations**:
   - `c2d9cf951ddc` (rent item types)
   - `9b0e06f05fcf` (rent item types support)
   - `2765a36d76ff` (rent item types support)
   - `a1b2c3d4e5f6` (coverage period tracking)

3. **Restart application**:
   ```bash
   sudo systemctl restart classroom-token-hub
   ```

### Breaking Changes
None. This release is backward compatible.

---

## Testing

Verified with targeted rent item type flows, coverage-period rent checks, and regression validation for store and insurance scoping.

---

## What's Next

See [DEVELOPMENT.md](../../DEVELOPMENT.md) for the active roadmap.

---

**Last Updated**: 2026-02-09
**Release Status**: Released
