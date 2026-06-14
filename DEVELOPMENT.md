# Classroom Token Hub - Development Priorities

**Last Updated:** 2026-06-14
**Current Version:** 1.10.0 — Version 1 Final Release (End-of-Life)
**Status:** V1 retired. No further v1 development planned. Active work is on Version 2.

---

## Quick Links

- **[Architecture Guide](docs/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md)** - System design and patterns
- **[Database Schema](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-007_Database_Schema.md)** - Current data models
- **[API Reference](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-005_Api_Reference.md)** - REST API documentation
- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute
- **[Project History](docs/LOGS/AUDITS/LOG-ARC-031_Project_History.md)** - Project evolution and philosophy

## Git Hooks

Run once after clone:

```bash
./scripts/setup-hooks.sh
```

This sets `core.hooksPath=hooks` and enables shared repo hooks, including branch-aware DB switching:

- Protected v2 branches (`join-code-centric-architecture-rebuild`, `codex/fix-database-model-for-dob-sum-storage`, `codex/v2.0`) -> `classroom_economy`
- All other branches -> `production_dev`

## Static Assets and Cache Busting

- Always reference CSS/JS/images in templates with `static_url('<path>')` so Flask appends a file timestamp query parameter.
- Avoid hard-coding `/static/...` paths or `url_for('static', ...)` in templates; the helper prevents browsers/CDNs from serving stale assets after deployments.

---

## Shipped in v1.10.0 (Final Release — June 14, 2026)

The following shipped to `main` since v1.9.0 and are included in the final v1.10.0 tag:

- **Runtime Invariant Health Check System** (V2-INV-001) — `GET /health/invariants` endpoint validates six economic and ledger invariants continuously. `transfer_correlation_id` added to `transaction` to link transfer pairs. See `docs/INV-CORE-000_Core_Invariants.md`.
- **Student DOB Privacy Remediation (Phase 1)** — DOB removed from usernames and logs; one-time migration flow at `/migrate-username`; `username_migrated` boolean on `Student`; `dob_sum` and `last_name_hash_by_part` nulled post-migration.
- **V1 Rent Stabilization** — Centralized payment validation, atomic transaction boundary, pre-insert guard, duplicate submission soft guard, anomaly logging. See `docs/FEATURES/RENT/FEAT-RENT-004_V1_Stabilization_Plan.md`.
- **Tiered Insurance Setup** — Modular preset/advanced/custom configuration modes; lock-in workflow; economy snapshot pricing; variable approval cap fix.
- **Economy Policy Mode and Rebalancer** — `Tight` / `Default` / `Comfortable` profiles drive CWI-guided rebalance for rent, store, insurance, and payroll settings.
- **Teacher PII Deletion Cascade** — Explicit FK-ordered cascade cleanup on teacher account deletion prevents `ForeignKeyViolation` errors.
- **Gunicorn Structured JSON Logging** — Machine-readable access logs with configurable local-timezone timestamps; Grafana economy-health dashboard added.
- **Sysadmin escalated issue "In Review" status** — New status for active-investigation state before resolution.
- **Collective goal progress reset on reactivation** — Reactivating a deactivated collective goal now starts progress at zero.
- **Rent waiver UI class switching fix** — Waiver form reloads correctly when the teacher switches the active class.
- **Rent full-payment mode fix** — Corrected blocking of already-paid students in full-payment mode.
- **Insurance claim time-limit gate** — Uses filing timestamp; teacher override available.
- **Privacy policy accuracy revision** — Hashing description, retention windows, and recovery flow description corrected.

---

## Recent Releases

### ✅ Version 1.10.0 — Final Release (June 14, 2026)

Final v1 release. All work that shipped since v1.9.0 is tagged here. See [CHANGELOG.md](CHANGELOG.md) for the complete entry.

Key areas: runtime invariant health checks, student DOB privacy remediation, V1 rent stabilization, tiered insurance setup, economy policy mode and rebalancer, teacher PII deletion cascade, Gunicorn JSON logging, insurance recurring billing phases 2–4, v1 sunset transition gate.

### ✅ Version 1.9.0 - March 4, 2026

**Documentation taxonomy and navigation integrity release:**

#### 🎯 Key Accomplishments
- ✅ **Taxonomy Consolidation** - Migrated docs into canonical namespaces and standardized paths
- ✅ **Docs Navigation Fixes** - Repaired docs routes, links, breadcrumbs, and dotted filename handling
- ✅ **Audience Toggle** - Added user/devops audience filtering in docs views/search
- ✅ **Rendering Hardening** - Improved front matter detection and markdown parsing safeguards

See [LOG-REL-016_Release_Notes_V1.9.0.md](docs/LOGS/RELEASES/LOG-REL-016_Release_Notes_V1.9.0.md) for full details.

### ✅ Version 1.8.0 - February 9, 2026

**Major feature release focused on rent item types, coverage tracking, and stability fixes:**

#### 🎯 Key Accomplishments
- ✅ **Rent Item Types** - Added privilege, per-use, and hall pass rent item types with store integration and usage tracking
- ✅ **Pre-Paid Rent Coverage Tracking** - Rent payments now record coverage period and drive all rent checks
- ✅ **Store & Rent Stability Fixes** - Fixed duplicate rent-linked store items and rent purchase blocking across month boundaries
- ✅ **Insurance Class Scoping** - Fixed insurance management filters to respect selected class period
- ✅ **Security Hardening** - Improved Grafana proxy content-type filtering to prevent XSS

See [RELEASE_NOTES_v1.8.0.md](docs/LOGS/RELEASES/LOG-REL-015_Release_Notes_V1.8.0.md) for full details.

### ✅ Version 1.7.0 - January 9, 2026

**Major feature release focused on system health analytics, flexible rent options, and mobile accessibility:**

#### 🎯 Key Accomplishments
- ✅ **Analytics Dashboard** - System health observability with CWI-relative metrics
- ✅ **Rent Itemization** - Teachers can specify what rent pays for with store alternatives
- ✅ **Mobile Navigation** - Full navigation menu accessible on mobile and PWA
- ✅ **Rent Privilege Badges** - Visual indicators for active rent privileges
- ✅ **Purchase Duration Options** - Per-use vs per-period choices for rent items
- ✅ **Code Quality Improvement** - Simplified redundant logic in `_add_period` utility function
- ✅ **Enhanced Purchase Restrictions** - Dynamic behavior based on rent itemization
- ✅ **ToS Acknowledgment** - Compliance modal during admin signup
- ✅ **Issue Resolution Improvements** - EasyMDE form fixes and zero-value event display

See [RELEASE_NOTES_v1.7.0.md](docs/LOGS/RELEASES/LOG-REL-013_Release_Notes_V1.7.0.md) for full details.

### ✅ Version 1.6.0 - January 1, 2026

**Repository organization and stability release:**

#### 🎯 Key Accomplishments
- ✅ **Repository Organization** - Consolidated duplicate files and improved documentation structure
- ✅ **Multi-Tenancy Fixes** - Fixed critical HallPassSettings violations
- ✅ **Passkey Authentication Fixes** - Improved environment variable loading and error handling
- ✅ **Documentation Updates** - Standardized file paths and references

See [RELEASE_NOTES_v1.6.0.md](docs/LOGS/RELEASES/LOG-REL-012_Release_Notes_V1.6.0.md) for full details.

### ✅ Version 1.5.0 - December 29, 2025

**Issue reporting and resolution system:**

#### 🎯 Key Accomplishments
- ✅ **Issue Resolution System** - Structured, teacher-mediated issue handling
- ✅ **Attendance Issue Reporting** - Students can report issues with tap events
- ✅ **Security Hardening** - Comprehensive attack surface audit and remediation
- ✅ **Time Handling** - Standardized UTC timestamp formatting

See [RELEASE_NOTES_v1.5.0.md](docs/LOGS/RELEASES/LOG-REL-011_Release_Notes_V1.5.0.md) for full details.

### ✅ Version 1.4.0 - December 27, 2025

**Major feature release focused on classroom communication and UI/UX enhancements:**

#### 🎯 Key Accomplishments
- ✅ **Announcement System** - Teachers can create and manage announcements for class periods
- ✅ **UI/UX Redesign** - Personalized greetings, enhanced dashboards, accordion navigation
- ✅ **Enhanced Security** - Fixed open redirect vulnerabilities and Grafana access issues
- ✅ **Streamlined Authentication** - Improved login flow with better error handling
- ✅ **Student Dashboard Improvements** - Side-by-side account cards with projected interest

See [RELEASE_NOTES_v1.4.0.md](docs/LOGS/RELEASES/LOG-REL-010_Release_Notes_V1.4.0.md) for full details.

### ✅ Version 1.3.0 - December 25, 2025

**Major security-focused release with passwordless authentication:**

#### 🎯 Key Accomplishments
- ✅ **Passwordless Authentication** - WebAuthn/FIDO2 passkey support for teachers and system admins
- ✅ **Encrypted TOTP Secrets** - TOTP 2FA secrets now encrypted at rest using Fernet
- ✅ **Security Audit** - Comprehensive attack surface security audit completed
- ✅ **Service Worker Fixes** - Resolved persistent browser console errors

See [RELEASE_NOTES_v1.3.0.md](docs/LOGS/RELEASES/LOG-REL-009_Release_Notes_V1.3.0.md) for full details.

### ✅ Version 1.2.0 - December 18, 2025

**Major feature release focused on mobile experience and accessibility:**

#### 🎯 Key Accomplishments
- ✅ **Progressive Web App (PWA) Support** - Full installable mobile app experience
- ✅ **Mobile-First UI** - Dedicated mobile templates with responsive navigation
- ✅ **Accessibility Improvements** - Comprehensive enhancements following WCAG 2.1 AA guidelines
- ✅ **UI Modernization** - Accordion-based admin templates for better organization
- ✅ **Critical Payroll Fix** - Resolved multi-tenancy data leak in payroll system
- ✅ **Improved Terminology** - "Start Work/Break Done" replaces "Tap In/Out"

See [RELEASE_NOTES_v1.2.0.md](docs/LOGS/RELEASES/LOG-REL-007_Release_Notes_V1.2.0.md) for full details.

### ✅ Version 1.0.0 - November 29, 2024

**First stable release - all critical blockers resolved:**

- ✅ **P0: Same-Teacher Multi-Period Data Leak** - Resolved with proper join_code scoping
- ✅ **P1: Deprecated Code Patterns** - Updated for Python 3.12+ and SQLAlchemy 2.0+

---

## V1 Retirement Notice

Version 1 is **retired as of June 14, 2026**. The items below were open at time of retirement. They are deferred to v2 or recorded here for historical reference — no v1 work will proceed on them.

### Deferred to V2 (not v1 issues)

- **Multi-Teacher Hardening** — Legacy `students.teacher_id` removal, NOT NULL enforcement on `join_code` in ledger tables, and `student_teachers` constraint runbook. The v2 schema redesign addresses these at the foundation level.
- **Shared-Student Test Coverage** — Payroll/attendance flows for multi-teacher students. v2 will re-test from scratch.
- **Data Export Capabilities** — CSV exports for rosters, transactions, attendance, payroll, and store purchases.
- **Enhanced Student Dashboard Insights** — Balance history graphs and projected earnings breakdowns.

### Known Issues at Retirement (P2 and below)

- SQLAlchemy `Query.get` usage surfaces `LegacyAPIWarning` during tests. Not addressed in v1; v2 uses the new ORM session API throughout.

### Items Explicitly Closed at V1 Retirement

- **Custom Condition Builder** — Deferred at v1.7; will not be added to v1. Candidate for v2 if demand warrants.
- **Jobs Feature** — Removed from v1 during cleanup; git history preserved at commit `0800640`. Not returning to v1.
- **Operational Safety Runbooks** — Partial; v1 migration runbooks remain in `docs/STANDARD_OPERATING_PROCEDURES/DATABASE/`. No further v1 updates planned.

---

## Historical Roadmap (Archived)

### Version 1.1 - Analytics & Insights ✅ **RELEASED 2024-12-13**
- ✅ Dashboard visualizations for student progress (weekly stats card with attendance, earnings, spending)
- ✅ Savings projection graph with interactive 12-month forecast
- ✅ Class economy health metrics (enhanced warnings with specific recommendations)
- ✅ Long-term goal items feature for flexible store pricing
- ✅ Complete UI redesign with modern, accessible interface
- 🔄 Teacher analytics for payroll and store performance (partial - economy health page provides CWI analysis)
- ⏳ Enhanced reporting and export capabilities (planned for future release)

**See:** [RELEASE_NOTES_v1.1.0.md](docs/LOGS/RELEASES/LOG-REL-005_Release_Notes_V1.1.0.md) for complete details

### Version 1.2 - Mobile Experience
- Progressive Web App (PWA) capabilities
- Native mobile app exploration
- Offline support for attendance tracking
- Improved touch interfaces

### Version 1.3 - Gamification
- Achievement badge system
- Optional leaderboards (privacy-conscious)
- Progress tracking and milestones
- Student engagement metrics

### Version 1.4 - Extended Features
- Curriculum integration resources
- Pre-built lesson plans
- Financial literacy assessment tools

### Version 2.0 - Internationalization
- Multi-language support
- Currency localization
- Regional educational standard alignment

### Planned Features (Future Releases)

#### 1. In-App Communication & Announcements ✅ **COMPLETED in v1.4.0**
**Status:** Implemented and released
**Documentation:** See release notes for v1.4.0

**Implemented Features:**
- **Teacher announcements** - Create and manage announcements for class periods
- **System-wide announcements** - System admin can broadcast to all users
- **Display on dashboards** - Students see announcements with dismiss capability
- **Period filtering** - Announcements scoped by class period
- **Visibility toggle** - Active/inactive announcement management

**Routes Implemented:**
- Teacher: `/admin/announcements` (list, create, edit, delete)
- System Admin: `/sysadmin/announcements` (global announcements)

#### 2. Teacher Self-Serve Account Recovery (Future)
**Status:** Documented, deferred due to security complexity
**Documentation:** `docs/ARCHITECTURE/SYSADMIN/ARC-SYS-001_Sysadmin_Interface.md` (mentions TOTP reset)

**Problem:** Teachers who lose access to their TOTP authenticator app are locked out of their accounts. Currently requires sysadmin intervention.

**Security Challenge:** Self-serve recovery requires storing additional sensitive information, which conflicts with the platform's minimal-PII philosophy.

**Potential Approaches:**
- **Backup codes** (one-time use) - Requires secure storage and user safekeeping
- **Recovery email** - Additional PII to protect, phishing risk
- **Security questions** - Generally weak security, social engineering risk
- **SMS verification** - More PII, SIM-swapping attacks
- **Printable recovery key** - User responsibility to secure physical key

**Current Approach:** Teachers recover access through student-assisted recovery, or create a new account if recovery is not possible.

**Estimated Effort:** 3-4 weeks (implementation) + security review
**Priority:** Medium (nice-to-have, but the current recovery model is intentional by design)
**Blocker:** Requires decision on acceptable security/PII tradeoffs

**Recommendation:** Keep the current recovery design unless there is a security-reviewed requirement to expand recovery options.

#### 1. Custom Condition Builder (v1.7+)
**Status:** Research completed, deferred to future release

**Description:** Drag-and-drop visual rule builder for custom conditional logic in rent, insurance, store, payroll, and banking features.

**Use Case:** Teachers could define custom triggers like "IF checking balance < $50 AND no insurance THEN charge $5 late fee"

**Implementation Options:**
- Phase 1: JSON-based rules engine with simple form builder (4-6 weeks)
- Phase 2: Enhanced drag-and-drop UI with SortableJS (2-3 weeks)
- Phase 3: Full Blockly integration for visual programming (4-6 weeks)

**Rationale for Deferral:** Power-user feature, not critical for core functionality; prioritize high-demand features first

**Estimated Effort:** 12-18 weeks for full implementation

#### 3. Collective Goals Store Items ✅ **COMPLETED in v1.9.0**
**Status:** Fully implemented
**Documentation:** See store-items user guide and CHANGELOG [1.9.0]

**Implemented:**
- Teacher UI for creating/editing collective goal items (store management)
- Optional expiration deadline: unmet goals auto-refund and deactivate on deadline
- Progress resets to zero on reactivation (voided `StudentItem` records excluded)
- `collective_goal_expires_at` column on `StoreItem` (migration `e3f4g5h6i7j8`)
- `app/utils/store.py`: `refund_pending_collective_purchases()` and `process_expired_collective_goals()` helpers
- 71+ tests in `tests/test_collective_goal_expiration.py`

#### 4. Jobs Feature (v1.7+)
**Status:** Partially implemented, then removed; awaiting completion
**Git History:** Started in commit `0800640`, removed in commit `a04b574` (2025-12-10)

**Description:** Classroom job market system allowing teachers to create job opportunities for students, teaching work ethic and providing earning opportunities beyond attendance-based payroll.

**Two Job Types:**

1. **Employee Jobs** - Long-term positions with regular pay
   - Application and approval process required
   - Regular salary payments (daily/weekly/monthly)
   - Multiple vacancy slots per job
   - Job requirements and qualifications
   - Termination system with notice periods, warnings, and penalties
   - Teacher can fire employees with configurable consequences

2. **Contract Jobs** - One-off bounties, first-come-first-served
   - No application required; students claim available contracts
   - Single bounty payment upon completion
   - Quick turnaround for short-term tasks
   - Teacher marks as complete to trigger payment

**Database Models Created:**
- `JobTemplate` - Reusable job definitions in the teacher's job bank
- `Job` - Instance of a template assigned to a specific period/block
- `JobApplication` - Student applications for employee positions
- `JobEmployee` - Active employment relationships
- `JobContract` - Contract job assignments and completions

**Features Implemented Before Removal:**
- Job bank management for teachers (create/edit templates)
- Job assignment to specific class periods via join_code
- Application system for employee positions
- Contract claiming interface
- Payment processing integration with transactions
- Termination system with warnings and penalties
- Comprehensive test coverage (test files removed with feature)
- Admin routes (`app/routes/admin_jobs.py`, 514 lines)
- Flask forms for all job operations

**Use Cases:**
- **Classroom Helper:** Student job as "Board Eraser" earning $5/week
- **Technology Assistant:** "Chromebook Manager" earning $10/week
- **Project Bounties:** "Design Class Poster" contract for $25 one-time
- **Teaching Work Ethic:** Students learn reliability, job performance, consequences of termination
- **Earning Diversity:** Income beyond attendance, rewarding contribution and responsibility

**Why It Was Removed:**
- Removed during feature cleanup (commit a04b574)
- Only merge migration kept to maintain migration chain integrity
- Code preserved in git history for future reimplementation

**Remaining Work for Completion:**
- [ ] Restore models from commit `0800640`
- [ ] Restore admin routes from commit `e2de8bd`
- [ ] Restore Flask forms from commit `c9378b7`
- [ ] Restore test coverage from commit `8a1b0bd`
- [ ] Update for current join_code scoping patterns
- [ ] Add student-facing job board interface
- [ ] Add application submission and tracking UI
- [ ] Implement contract claiming interface
- [ ] Add job performance tracking (optional: attendance link)
- [ ] Create teacher analytics for job market health

**Estimated Effort:** 6-8 weeks (restoration + modernization + UI polish)
**Priority:** Medium (valuable feature, but not critical for 1.0)
**Complexity:** High (payroll integration, multi-state workflows, termination rules)

**Git References:**
- `0800640` - Add jobs feature database models and migration
- `c9378b7` - Add Flask forms for jobs feature
- `e2de8bd` - Add admin routes for jobs feature (514 lines)
- `8a1b0bd` - Add comprehensive tests and documentation for jobs feature
- `a04b574` - Remove jobs feature code, keep only merge migration
- `e7b38b9` - Fix migration chain: add stub for removed jobs feature migration

---

## Recently Completed Features

### April 2026
- ✅ Student DOB Privacy Remediation Phase 1 (2026-04-12) — DOB removed from usernames and logs; one-time `/migrate-username` flow; `username_migrated` flag; `dob_sum` nulled post-migration
- ✅ V1 Rent Stabilization — centralized payment validation, atomic transaction boundary, pre-insert guard, duplicate submission soft guard, anomaly logging (PR #1156)
- ✅ Runtime Invariant Health Check System (V2-INV-001) — `GET /health/invariants` with 6 invariant categories; `transfer_correlation_id` on transactions (PR #1138, #1139)
- ✅ Teacher account deletion explicit cascade — FK-safe multi-table cleanup prevents ForeignKeyViolation (PR #1157)
- ✅ Gunicorn structured JSON access logging (PR #1157)
- ✅ Sysadmin "In Review" escalated issue status

### March 2026
- ✅ Collective goal expiration deadline and progress reset on reactivation (PR #1110, v1.9.0)
- ✅ Economy policy mode and rebalancer — `Tight`/`Default`/`Comfortable` profiles (v1.9.x)
- ✅ Tiered insurance setup with lock-in workflow (PR #1090–#1096, v1.9.x)
- ✅ Rent waivers properly scoped to `join_code` and honored in payment validation (v1.9.x)
- ✅ Rent cycle rate lock per `join_code` — mid-cycle changes roll to next cycle (PR #1103, #1104)

### December 2025
- ✅ Teacher display names and custom class labels (2025-12-06)
  - Added `display_name` to Admin model
  - Added `class_label` to TeacherBlock model
  - Created teacher settings page at `/admin/settings`
  - Responsive navigation (icon-only mode on mobile)
- ✅ Economy balancing system with CWI calculations
- ✅ Store item pricing tiers
- ✅ Block-scoped payroll settings

### November 2025
- ✅ Same-teacher multi-period data leak fix (2025-11-29)
- ✅ Configurable payroll settings with advanced schedule/rate options
- ✅ Insurance policies, enrollments, and claims flows
- ✅ Student/teacher sharing via `student_teachers` with scoped queries
- ✅ Join-code roster claiming using `TeacherBlock` seats
- ✅ Documentation reorganization and cleanup

---

## Multi-Tenancy Architecture

### Current State

#### Join Code as Source of Truth
- **Class Isolation:** Join codes partition transactions/attendance between class periods
- **Student Sessions:** Persist `current_join_code` to scope balances/transactions per class
- **Authoritative Model:** `student_teachers` link table enforces ownership
- **Deprecated:** `students.teacher_id` is ignored by access control helpers

#### Access Control
- **Scoped Helpers:** `get_admin_student_query`, `get_student_for_admin` in `app/auth.py`
- **Admin Routes:** Use scoped helpers exclusively (avoid direct `Student.query`)
- **System Admins:** Global visibility across all students and teachers
- **Teacher Isolation:** Each teacher sees only their linked students

#### Database Constraints
- **Uniqueness:** `student_teachers` enforces (`student_id`, `admin_id`) unique constraint
- **Cascading:** Deletes cascade properly through relationships
- **Join Code:** NOT NULL enforcement pending after backfill verification

### Migration Strategy

When ready to finalize multi-teacher model:

1. **Pre-checks:**
   - Verify every student has ≥1 `student_teachers` row
   - Identify orphaned student records
   - Audit direct `Student.query` usage in codebase

2. **Maintenance Banner:**
   - Enable maintenance mode during migration if medium/high risk
   - Use `MAINTENANCE_MODE=true` environment variable

3. **Migration Execution:**
   - Drop/lock `students.teacher_id` after dependency verification
   - Ensure foreign keys optimized for scoped queries
   - Enforce `join_code` NOT NULL on ledger tables

4. **Post-checks:**
   - Smoke tests on admin/student portals
   - Validate payroll/attendance with shared students
   - Verify no routes bypass scoped helpers

---

## Code Quality Standards

### Authentication & Authorization
- Prefer scoped helpers (`get_admin_student_query`, `get_student_for_admin`) over ad-hoc filters
- Always check `is_system_admin` for global access requirements
- Use `@admin_required` and `@system_admin_required` decorators consistently

### Database Best Practices
- **Migrations:** Always sync with main before creating new migrations
- **Queries:** Use scoped helpers for tenant-aware access
- **Timestamps:** Use `datetime.now(timezone.utc)` (not deprecated `utcnow()`)
- **Session Access:** Use `db.session.get(Model, id)` (not deprecated `Model.query.get()`)
- **Schema Changes:** See **[Migration Best Practices](docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-011_Migration_Specifications.md)** for the mandatory "Expand and Contract" workflow.

### Safe Schema Evolution (Constraint & Column Removal)
**CRITICAL:** Adopt the **Expand and Contract** pattern. Attempting to delete Code + DB in the same release is PROHIBITED.
1.  **Release 1 (Expand):** App supports new schema; old schema remains and is ignored.
2.  **Release 2 (Contract Code):** Remove attribute from Model. Database column stays. Hidden dependencies will crash loudly but are reversible.
3.  **Release 3 (Contract DB):** Migration drops the column.

### Testing Policy for Refactors
- **No Mechanical Fixes:** If a test breaks due to a signature change (e.g., removing `teacher_id` from constructor), you must review the **entire test logic**. Simply removing the argument is forbidden.
- **Workflow Coverage:** Critical flows (Claims, Transfers, Admin Ops) require integration tests before schema changes.

### Security Guidelines
- Keep PII minimal (prefer non-PII identifiers, encrypted first names)
- Validate all user input at route level
- Use CSRF protection on all forms
- Encrypt sensitive data at rest
- Avoid adding debug print statements to production code


### Testing Requirements
- Run `pytest -q` before committing
- Add tests for new features and bug fixes
- Focus tests for tenancy helpers when changing scoping logic
- Ensure foreign key constraints enabled in tests

---

## Development Workflow

### Before Creating Migrations

**⚠️ CRITICAL: Always follow this workflow to prevent multiple heads:**

1. **Sync with latest code:**
   ```bash
   git fetch origin main
   git merge origin/main
   ```

2. **Verify exactly ONE migration head:**
   ```bash
   flask db heads  # Must show exactly 1 head
   ```

3. **If multiple heads exist, merge them first:**
   ```bash
   flask db merge heads -m "Merge migration heads"
   ```

4. **Check current revision:**
   ```bash
   flask db current
   ```

5. **Create migration:**
   ```bash
   flask db migrate -m "Clear description"
   ```

6. **Verify new migration:**
   - Open generated file in `migrations/versions/`
   - Verify `down_revision` matches `flask db current` output
   - If mismatch, DELETE migration and restart workflow

7. **Test migration:**
   ```bash
   flask db upgrade    # Apply
   flask db downgrade  # Rollback
   flask db upgrade    # Reapply
   ```

8. **Quick verification:**
   ```bash
   bash scripts/check-migration-heads.sh
   ```

### Before Submitting PR

- [ ] Tests pass locally (`pytest -q`)
- [ ] Migrations reviewed for safety (lock impact, backfill steps)
- [ ] No new deprecation warnings
- [ ] Code follows project conventions
- [ ] Documentation updated where needed
- [ ] Commit messages are clear and descriptive

---

## Effort Snapshot

| Priority | Focus Areas | Notes |
|----------|-------------|-------|
| 🟠 High | Multi-teacher hardening, shared-student tests, migration runbooks | Coordination with ops needed before schema changes |
| 🟡 Medium | UX polish, exports, accessibility | Design alignment required |
| 🟢 Lower | Insights, performance, notifications | Schedule after core hardening |

---

## Documentation Structure

### User Documentation
- **[Student Guide](docs/user-guides/student_guide.md)** - How students use the platform
- **[Teacher Manual](docs/user-guides/teacher_manual.md)** - Comprehensive admin guide

### Technical Reference
- **[Architecture](docs/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md)** - System design and patterns
- **[Database Schema](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-007_Database_Schema.md)** - Data models and relationships
- **[API Reference](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-005_Api_Reference.md)** - REST endpoints
- **[Timezone Handling](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-012_Datetime_Handling_Specification.md)** - UTC storage and conversion
- **[Economy Specification](docs/DOMAINS/ECONOMY_DESIGN/DOM-ECON-002_Economy_Specification.md)** - Financial system ratios and rules

### Development Guides
- **[Economy Balance Checker](docs/DOMAINS/ECONOMY_DESIGN/DOM-ECON-001_Economy_Balance_Checker.md)** - CWI implementation guide
- **[Migration Guide](docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-011_Migration_Specifications.md)** - Alembic best practices
- **[Migration Best Practices](docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-011_Migration_Specifications.md)** - Database migration guidelines
- **[Seeding Instructions](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-020_Seeding_Instructions.md)** - Test data setup
- **[Deprecated Patterns](docs/LOGS/AUDITS/LOG-ARC-036_Deprecated_Code_Patterns.md)** - Code modernization tracking
- **[System Admin Design](docs/ARCHITECTURE/SYSADMIN/ARC-SYS-001_Sysadmin_Interface.md)** - Admin interface patterns

### Operations & Deployment
- **[Deployment Guide](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-006_Deployment_Guide.md)** - Production deployment
- **[Operations Guides](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/)** - Maintenance procedures
- **[Security Audits](docs/SECURITY/)** - Security assessment reports

### Historical Reference
- **[Project History](docs/LOGS/AUDITS/LOG-ARC-031_Project_History.md)** - Evolution and philosophy
- **[Changelog](CHANGELOG.md)** - Version history
- **[Archive](docs/LOGS/AUDITS/)** - Historical reports and fixes

---

## Success Metrics for 1.0 Release

Version 1.0 has been successfully released with the following criteria met:

1. ✅ All P0 and P1 issues resolved
2. ✅ Full test suite passes (100% of existing tests)
3. ✅ No known security vulnerabilities
4. ✅ Codebase uses modern Python 3.12+ and SQLAlchemy 2.0+ patterns
5. ✅ Staging environment validated
6. ✅ Production deployment successful
7. ⏳ No critical bugs reported within 48 hours of release (Monitoring)
8. ✅ Documentation complete and accurate
9. ✅ Rollback plan tested and ready

**Status:** 1.0.0 RELEASED!

---

## Getting Help

- **Documentation Issues:** Check [docs/README.md](docs/README.md) for navigation
- **Technical Questions:** Review [Architecture Guide](docs/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md)
- **Security Concerns:** See [Security Audits](docs/SECURITY/)
- **Contributing:** Read [CONTRIBUTING.md](CONTRIBUTING.md)

---

**V1 is complete. No further actions are planned for v1.**

For v2 architectural direction, see the v2 development branch and the v2 design documents in `docs/ARCHITECTURE/`.

Key v2 follow-up items carried forward from v1 design learnings:
- Rebuild attendance tap-in/tap-out enforcement around explicit session ownership and stronger boundary semantics: persist the effective attendance timezone with the session/class, close cross-day sessions deterministically, and unify manual tap, dashboard status refresh, hall-pass transitions, and scheduled auto-tap-out behind one authoritative state machine so cap enforcement and day-boundary enforcement cannot drift apart.
- Ground-up join-code-centric schema (no legacy `teacher_id` on students from day one).
- DOB-free identity verification by design.

**V1 Release History:**
- **v1.10.0** (2026-06-14) - **Final Release — V1 Retired**
- **v1.9.0** (2026-03-04) - Docs Taxonomy Consolidation and Navigation Integrity
- **v1.8.0** (2026-02-09) - Rent Item Types, Coverage Tracking, Stability Fixes
- **v1.7.0** (2026-01-09) - Analytics, Rent Itemization, Mobile Navigation
- **v1.6.0** (2026-01-01) - Repository Organization
- **v1.5.0** (2025-12-29) - Issue Resolution System
- **v1.4.0** (2025-12-27) - Announcement System, UI/UX Redesign
- **v1.3.0** (2025-12-25) - Passkey Authentication, Encrypted TOTP
- **v1.2.0** (2025-12-18) - PWA, Mobile-First UI, Accessibility
- **v1.1.0** (2025-12-13) - Analytics & Insights
- **v1.0.0** (2024-11-29) - First Stable Release

---
**Last Updated:** 2026-06-14
**Maintained by:** Project maintainers and contributors
