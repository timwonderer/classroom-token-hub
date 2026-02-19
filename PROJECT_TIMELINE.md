# Comprehensive Project Timeline: Classroom Token Hub

## Executive Summary

**Classroom Token Hub** is an educational banking simulation platform built by a full-time high school teacher to teach financial literacy through hands-on classroom experience. The project has evolved from a simple concept to a production-grade multi-tenant system with 41 SQLAlchemy models, 83+ Alembic migrations, and comprehensive security hardening.

**Current Status:** v1.8.0 (Released February 8, 2026)
**Total Versions Released:** 8 major versions (v1.0 through v1.8)
**Development Timeline:** ~2 years (pre-2024 through 2026)
**Total Commits:** 68+ visible commits (recent commit history in current shallow clone)

---

## Project Eras: A Story in Four Acts

### ERA I: The Genesis & Foundation (Pre-2024 through November 2025)

**Theme:** *"I will just make it myself"*

This era represents the ideation, design, and initial construction of a tool to solve a real problem in a real classroom.

#### The Original Problem

The project originated from a fundamental gap in available educational technology: no platform existed that simulated classroom economies realistically while prioritizing financial literacy AND respecting student data privacy.

**Key Quote from PROJECT_HISTORY.md:**
> *"Becoming an app developer was never part of the plan, but rather a side project that has 'gone out of hand.' Every feature and design you see today was a product of countless 500 errors, tears, students' incessant 'Mr., it's not working!', and, of course, the satisfaction of seeing the puzzle pieces click into place."*

#### Core Design Decisions Crystallized

1. **Experience Before Explanation Philosophy**
   - Students understand systems after *feeling* them, not from lectures
   - Real consequences teach faster than warnings
   - Designed for lived participation, not passive learning

2. **Join Code as Source of Truth** (Critical decision)
   - Early designs tied students too closely to teacher accounts
   - Failed under real classroom conditions with multi-teacher students
   - Join code became the absolute source of truth for class isolation
   - This decision **reshaped the entire data model**

3. **Teacher Authority with System Transparency**
   - No invisible teacher overrides
   - No silent balance edits
   - Teachers bound by system like students
   - All actions visible to students (builds trust)

4. **Classroom Wage Index (CWI) Economy Stabilizer**
   - Unregulated classroom economies inflate or collapse
   - CWI prevents runaway wages and distorted prices
   - System learns to self-regulate

5. **Insurance Systems as Reality Response**
   - Attendance is not purely a moral choice; life interferes
   - Insurance handles legitimate absences
   - Punishment disguised as realism is neither accurate nor educational

#### Name Change: "Classroom Economy" → "Classroom Token Hub"

This wasn't just a rebranding; it represented a **philosophical shift from a gimmick to a persistent, interconnected system**. The new name reflected the platform's role as a hub for comprehensive financial literacy education.

#### Pre-Release Development: Building the Foundation

During this era, the project went through:
- Initial prototype development and refinement
- Real classroom testing with actual students (the best beta testers)
- Architectural design: modular blueprint structure, 41 SQLAlchemy models
- Security implementation: PII encryption, TOTP authentication, password hashing with salt and pepper
- Multi-tenancy architecture design (join_code as source of truth)
- Testing framework and CI/CD pipeline setup

#### Key Learnings from This Era

- Real students find real bugs that simulated testing would miss
- Security must be foundational, not retrofitted
- Multi-tenancy must be baked into the architecture from the start
- Experience-based pedagogy requires systems that enforce consequences
- Teacher friction with system design builds trust

---

### ERA II: Stability & Crisis Resolution (November 2025 - January 2026)

**Theme:** *"Fix First, Then Build"*

This era was dominated by discovering and resolving critical issues revealed through the first deployments.

#### v1.0.0 - December 11, 2025 (First Stable Release)

**CRISIS 1: P0 Same-Teacher Multi-Period Data Leak**

**Date Discovered:** Pre-release (November 2025, likely earlier)
**Severity:** CRITICAL
**Impact:** Students in multiple periods with same teacher saw aggregated data across all periods

**Root Cause:**
- `Transaction` model had `teacher_id` but not `join_code`
- Queries filtered by `teacher_id` only, returning all periods
- Fundamental privacy and fairness violation

**Resolution (Early December 2025, released in v1.0.0):**
- Added `join_code` to all financial tables
- Updated session management to track `current_join_code`
- Modified ALL queries to scope by `join_code`
- Created interactive backfill process for legacy transactions
- Added comprehensive regression tests for multi-tenancy isolation

**Lesson:** Multi-tenancy must be verified at the database level, not the application level. Join code is non-negotiable.

**CRISIS 2: P1 Deprecated Code Patterns**

**Severity:** HIGH (would break in Python 3.12+/SQLAlchemy 2.0+)
**Resolution (Completed December 6, 2025):**
- Replaced 52 occurrences: `datetime.utcnow()` → `datetime.now(timezone.utc)`
- Migrated `Query.get()` → `db.session.get(Model, id)`
- Achieved full Python 3.12+ and SQLAlchemy 2.0+ compatibility

#### Key Features Shipped in v1.0

- Multi-tenancy with join-code isolation
- Teacher account recovery (student-verified codes)
- System admin portal
- Comprehensive transaction audit trails
- Insurance policies (enrollment, claims, reimbursement)
- Rent collection system
- TOTP 2FA for all admins
- Dual accounts (checking + savings with interest)
- Classroom store with bundles
- Hall pass system with time tracking
- PII encryption at rest
- 55 comprehensive test files
- 83 Alembic migrations

#### v1.1.0 - December 13, 2025

**Theme:** Analytics & Insights

- **Student Analytics Dashboard** - Weekly statistics, days attended, earnings tracking
- **Savings Projection Visualization** - 12-month interactive growth projection
- **Long-Term Goal Items** - Teacher-designated expensive items exempt from CWI warnings
- **Economy Health Dashboard** - Specific recommended ranges with actionable guidance
- **Complete UI Redesign** - Modern colors, card-based layouts, responsive design
- Critical bug fixes: Invisible tabs, missing navigation links

#### v1.1.1 - December 14, 2025

**Theme:** Security Hardening v1

- Secured teacher recovery with hashed DOB
- Hardened student login redirects
- Fixed insurance management crashes
- Added cache-busting for static assets

#### The Great Decimal Precision Crisis (January 2026)

**Problem Discovered:** Floating-point precision errors accumulating in financial calculations

**Symptoms:**
- Transfers that zeroed checking accounts incorrectly triggered $35 overdraft fees
- Partial rent payments left unpayable tiny balances ($0.0000001)
- Dashboard interest calculations crashing with type errors

**Root Cause:**
- `Transaction.amount` stored as Float instead of Numeric
- Python float arithmetic: 0.1 + 0.2 ≠ 0.3 (IEEE 754 rounding errors)
- Mixed Decimal/float arithmetic caused TypeErrors

**Resolution (January 25, 2026 - v1.7.1):**
- Changed database: `Float` → `Numeric(12, 2)` across all financial models
- Systematic refactoring of ALL calculations to use Decimal type
- Added near-zero balance normalization (|balance| < $0.01 → $0.00)
- Maintains Decimal precision throughout, converts to float only at serialization

**Lesson:** Financial systems MUST use Decimal type, never Float. Precision errors compound invisibly and become hidden bugs.

---

### ERA III: Feature Expansion & Security Hardening (December 2025 - February 2026)

**Theme:** *"Build with Confidence"*

With critical issues resolved, the project entered rapid feature development with strong security and quality practices.

#### v1.2.0 - December 18, 2025

**Theme:** Mobile Experience & Accessibility

**Major Features:**
- **Progressive Web App (PWA) Support**
  - Full installable mobile app on iOS/Android
  - Service worker with intelligent caching
  - Offline fallback page
  - Auto cache cleanup and version management

- **Mobile-First Experience**
  - Dedicated mobile templates
  - Bottom tab navigation
  - 44x44px minimum touch targets
  - Responsive store interface

- **WCAG 2.1 AA Accessibility Compliance**
  - ARIA labels on interactive elements
  - Enhanced keyboard navigation
  - Improved color contrast
  - Screen reader compatibility
  - Skip-to-content links

- **Terminology Update:** "Tap In/Out" → "Start Work/Break Done"

**Critical Bug Fixed:** Multi-tenancy payroll bug where calculations leaked data across class periods

#### v1.2.1 - December 21, 2025

**Theme:** Legacy Account Migration

- Comprehensive migration script for `teacher_id` → claim-based enrollment
- Multi-period student scenario testing
- Join code schema audit tools
- Critical: Transaction backfill matches on BOTH `student_id` AND `teacher_id`

#### v1.3.0 - December 25, 2025

**Theme:** Security & Passwordless Authentication

**Major Features:**
- **Passwordless Authentication (WebAuthn/FIDO2)**
  - Hardware security keys support (YubiKey, Google Titan, etc.)
  - Platform authenticators (Touch ID, Face ID, Windows Hello)
  - Synced passkeys across devices
  - Teachers and system admins
  - Using official Bitwarden Passwordless SDK

- **Encrypted TOTP Secrets at Rest**
  - Fernet (AES-128-CBC) encryption
  - Database compromise alone insufficient for 2FA codes
  - Defense in depth layer

- **Security Audit: Comprehensive Attack Surface Review**
  - Identified and fixed 16 findings (2 critical, 2 high, 3 medium, 4 low, 5 informational)
  - **Critical Issue Fixed:** AI prompt injection in GitHub Actions (PromptPwnd vulnerability)
  - Immediate remediation (workflow disabled)
  - No exploitation detected

- **Removed Sensitive Information from Logs**
  - Eliminated username/hash logging from authentication flows
  - Removed student name and DOB logging from bulk uploads

#### v1.4.0 - December 27, 2025

**Theme:** Announcements & UI/UX Enhancements

**Major Features:**
- **Announcement System**
  - Teachers create/manage announcements for class periods
  - Students see announcements on dashboards with dismiss
  - System admins create global announcements
  - Rich formatting support

- **UI/UX Improvements**
  - Personalized greetings (teacher + student dashboards)
  - Side-by-side account balance cards
  - Savings account displays projected monthly interest
  - Accordion-style admin navigation
  - Streamlined authentication flow with two-method buttons

**Security Fixes:**
- CodeQL alerts remediation (62 alerts)
- Clear-text logging of TOTP secrets
- DOM XSS vulnerabilities
- GitHub Actions workflow permissions hardening
- Enhanced open redirect protection

#### v1.5.0 - December 29, 2025

**Theme:** Issue Resolution System & Escalation

**Major Features:**
- **Structured Issue Resolution Workflow**
  - Student submission interface (Knowledge Base, Report Issue, My Issues tabs)
  - Transaction-specific issue reporting
  - Attendance/tap event issue reporting
  - Automatic context capture (balances, transaction history, metadata)

- **Teacher Review & Escalation**
  - Issue review queue with status tracking
  - Resolution actions: reverse/void transactions, manual adjustment, deny
  - Escalation to developer with diagnostic notes
  - Privacy-conscious class name sharing option
  - "Student may receive reward" for legitimate bug reports

- **Technical Implementation**
  - 4 new models: `Issue`, `IssueCategory`, `IssueStatusHistory`, `IssueResolutionAction`
  - Multi-tenancy scoping by `join_code`
  - Context snapshots preserve ledger state
  - Complete audit trail
  - Opaque student references (hashed, non-reversible)

#### v1.6.0 - December 31, 2025

**Theme:** Repository Organization & Stability

- Documentation reorganization
- Multi-tenancy fixes (HallPassSettings NOT NULL violations)
- Passkey authentication environment variable fixes
- Getting Started widget fixes (database state instead of localStorage)

#### v1.7.0 - January 9, 2026

**Theme:** Analytics Dashboard, Rent Itemization, Mobile Navigation

**Major Features:**
- **Full Analytics Dashboard (CWI-Relative Metrics)**
  - System health observability
  - 3 new models: `AnalyticsSnapshot`, `AnalyticsEvent`, `AnalyticsAlert`
  - Metrics precomputed and cached by time window
  - Participation rate, money velocity, CWI deviation bands, budget survival
  - Trend analysis (improving/stable/worsening patterns)
  - Visual alerts with explanations and suggested actions
  - Weekly and monthly time windows
  - Design principle: "Something is drifting — and I know what lever to pull"

- **Mobile Navigation Enhancement**
  - Full navigation menu accessible on mobile (<768px)
  - Floating hamburger button with smooth slide-in animation
  - Backdrop overlay and auto-close on link click
  - Icon-only help buttons on mobile

- **Rent Itemization (MVP)**
  - `RentItem` model to track itemized components (e.g., Desk, Chair, Locker)
  - Optional store integration with automatic sync
  - Teachers can add/remove/reorder items
  - Store items inherit block visibility
  - Student rent view shows itemized breakdown

- **Purchase Duration Options**
  - Per-Use: Student buys each time (unlimited purchases)
  - Per-Rent-Period: Buys once, expires when rent due (limit 1)

- **Rent Privilege Badges**
  - Visual indicators on student detail pages
  - Green badges for rent-covered privileges
  - Blue badges for individually purchased privileges

#### v1.7.1 - January 25, 2026

**Theme:** Decimal Precision, Float/Decimal Type Fixes

**Critical Fixes:**
- Systematic Decimal refactoring of all financial calculations
- Fixed savings interest calculations
- Fixed dashboard earnings/spending analytics
- Fixed rent calculation accuracy
- Fixed rent statistics display
- Fixed hall pass queue scoping

**Result:** All financial calculations now mathematically exact

#### v1.8.0 - February 8, 2026

**Theme:** Rent Item Types, Coverage Tracking, Stability

**Major Features:**
- **Rent Item Types (Three Distinct Types)**
  - **Privilege:** Shows as badge on roster when paid; optionally in store
  - **Per-Use:** Grants free store redemptions with `uses_remaining` tracking
  - **Hall Pass:** Tops off student passes via `StudentBlock.rent_hall_passes`

- **Pre-Paid Rent Coverage Period Tracking**
  - Added `coverage_month` and `coverage_year` to `RentPayment`
  - Pays rent on due date (e.g., 1/28) covers from 1/29 to next due date
  - All checks use coverage-based lookups

- **Mid-Period Edit Guardrail**
  - Once any student paid rent: item type, use limits locked
  - Only cosmetic changes (name, description, price) allowed

- **Store Integration**
  - Per-use items marked `is_rent_linked`, preventing deletion
  - Admin store shows "Rent Perk" badge
  - Free purchase flow checks for rent-granted uses before charging

**Bug Fixes:**
- Privilege badges showing non-privilege rent items
- Insurance class selector not filtering data (multi-tenancy fix)
- Store purchase blocked after rent paid across month boundary
- Issue ticket filing with Decimal serialization error
- Duplicate store items when applying rent to all periods

**Security Hardening:**
- Grafana proxy XSS protection (case-insensitive Content-Type, blocked MIME types)
- Fixed function redefinition in student routes

---

### ERA IV: Refinement & Production Hardening (February 2026 - Present)

**Theme:** *"Toward v1.9 and Beyond"*

The current phase focuses on:
- Stabilization and performance optimization
- Removal of legacy code patterns
- Enhanced operational safety
- Preparation for v1.9 multi-teacher enhancements

#### Current Status (v1.8.0)

**Completed (Since v1.0):**
- ✅ P0 data leak fixed
- ✅ Full multi-tenancy scoping
- ✅ Passkey authentication
- ✅ Analytics dashboard
- ✅ Issue resolution system
- ✅ Rent itemization with types
- ✅ PWA and mobile support
- ✅ WCAG 2.1 AA accessibility
- ✅ 62+ security findings addressed

**In Progress (v1.9 Planning):**
- [ ] Multi-teacher hardening (finalize `student_teachers` migration)
- [ ] Remove legacy `students.teacher_id` (3-phase migration)
- [ ] Operational safety documentation
- [ ] Migration compliance re-audit

---

## Architectural Evolution

### The Journey from Monolith to Modular

**Pre-Release:** Monolithic 4,500-line `app.py`

**v1.0+:** Modular blueprint architecture
```
app/
├── __init__.py              # Application factory
├── models.py                # 41 SQLAlchemy models
├── auth.py                  # Access control helpers
├── routes/                  # Feature-scoped systems
│   ├── admin.py             # Teacher management
│   ├── student.py           # Student portal
│   ├── system_admin.py      # Platform administration
│   ├── api.py               # REST endpoints
│   └── auth.py              # Authentication flows
└── utils/                   # Shared constraints
    ├── economy_balance.py   # CWI and balance validation
    ├── payroll.py           # Payroll logic
    ├── attendance.py        # Attendance tracking
    └── ...
```

**Design Philosophy:** Blueprint isolation mirrors classroom section isolation

### Database Schema Evolution

| Version | Major Changes | Context |
|---------|---|---|
| Pre-1.0 | Initial schema design | Discovery phase with monolith |
| v1.0 | Added `join_code` to all financial tables | P0 data leak fix |
| v1.1 | Added analytics columns | Analytics dashboard |
| v1.2 | PWA schema (minimal changes) | Mobile support |
| v1.3 | Added `AdminCredential`, `SystemAdminCredential`; encrypted TOTP | Passkey authentication |
| v1.4 | Added `Announcement` model | Communication system |
| v1.5 | Added Issue models (`Issue`, `IssueCategory`, `IssueStatusHistory`, `IssueResolutionAction`) | Issue resolution system |
| v1.7 | Added `AnalyticsSnapshot`, `AnalyticsEvent`, `AnalyticsAlert`, `RentItem` | Analytics + rent itemization |
| v1.8 | Extended RentItem with types; added coverage tracking | Rent item types and coverage |

**Total Migrations:** 83+ (all with idempotency helpers as of v1.0)

---

## Critical Incidents & Resolutions

### Incident 1: P0 Same-Teacher Multi-Period Data Leak

**Status:** ✅ Resolved (November 2025)

**Impact:** Students saw aggregated financial data across class periods
**Root Cause:** Queries filtered by `teacher_id` only, not `join_code`
**Fix:** Database-level scoping by `join_code`, session tracking of `current_join_code`
**Lesson:** Multi-tenancy must be enforced at database level

### Incident 2: Floating-Point Precision Errors

**Status:** ✅ Resolved (January 25, 2026 - v1.7.1)

**Impact:** Overdraft fees on zero-balance transfers; unpayable tiny balances
**Root Cause:** Using `Float` instead of `Numeric` for financial amounts
**Fix:** Systematic Decimal refactoring across all calculations
**Lesson:** Financial systems require Decimal type, never Float

### Incident 3: AI Prompt Injection in GitHub Actions (PromptPwnd)

**Status:** ✅ Resolved (December 2025)

**Impact:** Potential for GITHUB_TOKEN leakage via workflow manipulation
**Root Cause:** Using `actions/ai-inference@v1` with untrusted user input
**Fix:** Immediately disabled vulnerable workflow, no exploitation detected
**Lesson:** AI/LLM tools in CI/CD are high-risk without sandboxing

### Incident 4: CodeQL Security Alerts

**Status:** ✅ Addressed (62 alerts - v1.4.0)

**Categories Fixed:**
- Clear-text logging of TOTP secrets
- DOM XSS vulnerabilities (innerHTML)
- GitHub Actions workflow permissions
- URL redirection bypasses

### Incident 5: Insurance Class Selector Multi-Tenancy Bug

**Status:** ✅ Resolved (v1.8.0)

**Impact:** Teachers with multiple periods saw all insurance data aggregated
**Root Cause:** Queries filtered by `teacher_id`, not `InsurancePolicyBlock` or `join_code`
**Fix:** Added proper `InsurancePolicyBlock` joins and `join_code` filtering

---

## Project Philosophy & Design Anti-Goals

### The Ten Anti-Goals (Features Intentionally NOT Built)

We are defined as much by what we refuse as by what we include:

1. **No XP Bars, Streaks, or Level-Ups** → Use earned wages instead
2. **No Perfect Attendance Bonuses** → Insurance system handles absences
3. **No Invisible Teacher Overrides** → All actions visible and logged
4. **No Behavior Scores or Compliance Metrics** → Neutral logs support conversations
5. **No AI Judgments of Student Intent** → No motivation predictions
6. **No Unlimited Configuration Knobs** → Guardrailed options maintain coherence
7. **No Frictionless Shortcuts** → Deliberate processes require acknowledgment
8. **No Leaderboards or Public Rankings** → Private balances protect dignity
9. **No Neutral-System Claim** → We acknowledge our assumptions openly
10. **No Direct Student-to-Sysadmin Support** → Teachers are first-line decision makers

### Core Educational Principles

1. **Experience Before Explanation** - Students understand after feeling systems
2. **Consequences Teach** - Real outcomes more instructive than warnings
3. **Fairness is Responsiveness** - System accounts for reality without pretending equality
4. **Agency Within Bounds** - Freedom meaningful only when bounded
5. **Teachers Bound by System** - If teachers exempt, simulation lies

---

## Key Metrics & Statistics

### Code Organization
- **41 SQLAlchemy Models** (v1.8.0)
- **83+ Alembic Migrations** (all idempotent as of v1.0)
- **55 Test Files** covering core functionality
- **35+ Routes** across all blueprints
- **Modular Architecture:** Refactored from 4,500-line monolith

### Quality & Testing
- **Foreign Key Constraints:** Enabled in all test databases
- **Multi-Tenancy Coverage:** Comprehensive join_code scoping tests
- **Legacy Compatibility:** Regression tests for deprecated patterns
- **Security Tests:** Authentication, authorization, encryption

### Documentation
- **Total Documentation Files:** 30+
- **Archive Documents:** 60+ (release notes, incident reports, PR reviews)
- **User Guides:** Teacher manual, student guide, economy guide
- **Technical Reference:** Architecture, database, API, economy spec
- **Operations Docs:** Deployment, monitoring, maintenance

### Security Posture
- ✅ TOTP + Passkey authentication (multi-factor)
- ✅ PII encryption (Fernet AES-128-CBC) at rest
- ✅ Password hashing with bcrypt + pepper (layered)
- ✅ CSRF protection on all forms
- ✅ SQL injection prevention (SQLAlchemy ORM exclusively)
- ✅ XSS mitigation (template escaping + CSP headers)
- ✅ Bot protection (Cloudflare Turnstile)
- ✅ Rate limiting (Flask-Limiter + Redis)
- ✅ Complete audit trails
- ✅ Data minimization

---

## Major Milestone Timeline

| Date | Version | Major Achievement | Impact |
|------|---------|---|---|
| Pre-2024 | Genesis | Project conceived and designed | Foundation for all future work |
| Nov 2025 | Pre-v1.0 | P0 data leak fixed | Multi-tenancy established |
| Dec 2025 | v1.0.0 | First stable release | Production-ready platform |
| Dec 2025 | v1.1.0 | Analytics dashboard shipped | Observability for teachers |
| Dec 2025 | v1.1.1 | Security hardening | Recovery system secured |
| Dec 2025 | v1.2.0 | PWA + Mobile + Accessibility | WCAG 2.1 AA compliant |
| Dec 2025 | v1.2.1 | Legacy account migration | Multi-teacher support |
| Dec 2025 | v1.3.0 | Passkey auth + Encrypted TOTP | Security audit completed |
| Dec 2025 | v1.4.0 | Announcements + UI redesign | Teacher communication |
| Dec 2025 | v1.5.0 | Issue resolution system | Structured escalation |
| Dec 2025 | v1.6.0 | Repository organization | Operational hygiene |
| Jan 2026 | v1.7.0 | Analytics dashboard + Rent items | Economic management |
| Jan 2026 | v1.7.1 | Decimal precision fixes | Financial accuracy |
| Feb 2026 | v1.8.0 | Rent item types + Coverage | Financial flexibility |

---

## Lessons Learned Across Eras

### Era I: Foundation (Pre-2024 → Nov 2025)
- Real students find real bugs that simulated testing misses
- Security must be foundational, not retrofitted
- Multi-tenancy requires architectural commitment from inception
- Experience-based pedagogy requires consequence enforcement

### Era II: Crisis Resolution (Nov 2025 → Jan 2026)
- Multi-tenancy must be verified at database level, not application level
- Financial systems require Decimal type; floating-point errors compound invisibly
- Legacy data migration demands careful planning and backfill validation
- Comprehensive testing prevents regressions during crisis fixes

### Era III: Expansion (Dec 2025 → Feb 2026)
- Security audits reveal systemic issues (62 CodeQL alerts → comprehensive fixes)
- Multi-tenancy is a living concern requiring constant vigilance
- Feature development doesn't slow when security is prioritized
- Teacher feedback drives UI/UX iterations

### Era IV: Refinement (Feb 2026 → Present)
- Production stability requires ongoing operational hygiene
- Legacy code removal is as important as new feature development
- Documentation of operational procedures prevents future incidents
- Data integrity safeguards (foreign keys, constraints) catch errors early

---

## Future Roadmap (v1.9+)

### High Priority (v1.9)
- [ ] Multi-teacher hardening (finalize `student_teachers` migration)
- [ ] Remove legacy `students.teacher_id` column (3-phase migration)
- [ ] Operational safety documentation and runbooks
- [ ] Migration compliance re-audit

### Medium Priority
- [ ] Admin experience polish (shared student UI)
- [ ] Data export capabilities (CSV exports)
- [ ] Mobile & accessibility enhancements (incremental)

### Lower Priority
- [ ] Enhanced student dashboard insights
- [ ] Performance profiling for large rosters
- [ ] Optional email notifications

### Post-1.0 Deferred Features
- [ ] **Jobs Feature** (models created pre-v1.0, removed, ready to restore)
- [ ] **Custom Condition Builder** (research completed, ~12-18 weeks)
- [ ] **Parent Portal** (privacy-controlled optional feature)
- [ ] **Collective Goals** (models + DB done, UI/workflows incomplete)
- [ ] **Internationalization** (multi-language support)

---

## Conclusion: What Makes This Project Unique

### The Arc of Development

1. **Phase 1 (Pre-v1.0):** Building core platform, discovering needs through real classroom use
2. **Phase 2 (v1.0-v1.2):** Fixing critical issues (P0 leak, deprecated patterns), adding PWA/accessibility
3. **Phase 3 (v1.3-v1.5):** Security hardening (passkeys, audits), comprehensive issue management
4. **Phase 4 (v1.6-v1.8):** Refinement (rent itemization, analytics, stability), moving toward v1.9

### Why This Project Matters

- **Built by an educator, for educators** — Not a generic LMS plugin adapted for classrooms
- **Designed for lived experience** — Students feel consequences in real-time
- **Prioritizes fairness over gamification** — No exploitative mechanics
- **Transparent by design** — Teachers and students see all transactions
- **Security-first architecture** — PII encryption, TOTP, passkeys, audit trails
- **Multi-tenancy from inception** — Supports complex school scenarios
- **Reversibility built-in** — Mistakes can be undone without breaking integrity
- **Non-commercial mission** — Educational use only (PolyForm Noncommercial License)

### The Quote That Defines It All

> *"Classroom Token Hub was created to fill the void of a platform that simulates an economy more realistically than what is available on the market. It also functions as a classroom management tool that teaches students personal responsibility. Most of all, it respects data privacy and security like no other. The friction you experience when creating, claiming, and resetting accounts was intentional. Classroom Token Hub does not ask, 'How can we defend ourselves?' It was designed to anticipate, 'What if the bad actor gets in?'"*

**Status:** Production-ready, with ongoing development toward v1.9 and beyond.

---

**Document Created:** February 17, 2026
**Last Updated:** February 17, 2026
**Next Review:** Post-v1.9 release
