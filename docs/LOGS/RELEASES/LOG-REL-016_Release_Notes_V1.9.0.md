# Release Notes - Version 1.9.0

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| LOG-REL-016      | 1.0     | 2026-03-04     | LOG-REL-015 | Informative                |

**Release Date**: March 4, 2026
**Focus**: Security hardening follow-through, account/recovery flow cleanup, performance stabilization, and documentation system consolidation

---

## Highlights

- **Security + Data Hygiene** - Completed class deletion hardening and post-claim PII minimization.
- **Recovery/Claim Simplification** - Student recovery flow reduced to join code + reset code, with roster identity preserved.
- **Performance Improvements** - Read-path optimization and scoped balance calculations stabilized high-volume class views.
- **Documentation v2 Alignment** - Moved remaining loose markdown into the new taxonomy and validated docs-site link integrity.

---

## Added

- **Collective goal expiration controls** for store items, including automatic refunds for unmet expired goals.
- **Admin transaction backfill workflow** (`/admin/backfill-transactions`) for legacy transactions missing `join_code`.
- **Interactive docs timeline** (`/docs/timeline`) with filterable release and architecture milestones.
- **System-admin consolidated views**:
  - `/sysadmin/combined-logs`
  - `/sysadmin/support`
  - Invite-code void route and open-ticket dashboard stat.

---

## Changed

- **Post-claim PII minimization**:
  - `TeacherBlock.dob_sum` / `last_name_hash_by_part` nulled on claim completion.
  - `Student.dob_sum` / `last_name_hash_by_part` nulled when credentials are finalized.
- **Student recovery flow simplification**:
  - Removed name/DOB re-entry from recovery.
  - `recovery.verify_identity` now forwards to account-lookup flow.
- **Documentation system migration to canonical taxonomy**:
  - Moved loose markdown artifacts into `docs/LOGS/AUDITS`.
  - Updated canonical index and release/archive navigation.

---

## Fixed

- **Class deletion safety and consistency**:
  - Removed stale `balance_cache` rows during join-code scope deletion.
  - Corrected sysadmin period-deletion scoping to join-code resolution.
  - Added orphaned settings cleanup for deleted block scopes.
- **Rent and store correctness**:
  - Prevented wrong-period rent prepayment under bill-preview scenarios.
  - Corrected rent transaction labeling to coverage period.
  - Preserved incremental rent payment UI behavior when enabled.
- **Attendance/payroll integrity**:
  - Added idempotency check for auto-tap-out daily-limit events to prevent duplicate payroll sessions.
- **Documentation site reliability**:
  - Fixed stale navigation routes, breadcrumb dead links, and dotted release-note route resolution.
  - Verified docs rendering and link integrity against the current docs taxonomy.

---

## Performance

- Removed write-on-read side effects from student balance properties.
- Optimized roster query patterns (N+1 elimination in student management list).
- Maintained strict class-scoped balance and payroll computations.

---

## Upgrade Notes

1. Pull latest code:
   ```bash
   git pull origin main
   ```
2. Run migrations:
   ```bash
   flask db upgrade
   ```
3. Restart application services:
   ```bash
   sudo systemctl restart classroom-token-hub
   ```

### Breaking Changes
None expected for standard deployments.

---

## Related References

- [Changelog](../../../CHANGELOG.md)
- [Releases Index](LOG-REL-003_Releases_Index.md)
- [Documentation Index](../../STANDARD_OPERATING_PROCEDURES/DOCUMENTATION/SOP-DOC-002_Documentation_Index.md)

---

**Last Updated**: 2026-03-04
**Release Status**: Released
