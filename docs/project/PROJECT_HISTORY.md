# Classroom Token Hub - Project History and Philosophy

Document Purpose: Preserve the history, philosophy, and key milestones of Classroom Token Hub.
Last Updated: 2026-01-04

---

## Project Vision and Philosophy

### Core Mission

Classroom Token Hub teaches financial literacy through a simulated classroom economy. Students earn, save, spend, and manage virtual currency tied to real classroom participation so they can practice money management in a safe environment.

### Educational Philosophy

1. Learning by doing. Students practice daily through attendance, payroll, savings and checking, and purchasing decisions.
2. Real-world simulation. Insurance, rent, interest, and transaction history mirror systems students will encounter later.
3. Teacher empowerment. Teachers have flexible tools to shape their classroom economies without sacrificing data integrity.
4. Student privacy. Personally identifiable information is encrypted at rest and access is scoped by class context.

### Design Principles

#### Join code as source of truth

A core architectural principle is:

"The class join code is the source of truth for how students are associated with a class."

This ensures:
- Students can participate in multiple class economies simultaneously.
- Data remains isolated between class periods and sections.
- Teachers can share students without cross-economy leakage.
- Class switching is deterministic and auditable.

#### Security-first development

Security has been a first-class concern from the start:
- Encrypted PII at rest
- TOTP and passkey authentication for admin roles
- CSRF protection on all forms
- Rate limiting on sensitive endpoints
- Input validation and sanitization

#### Educational use only

The project uses the PolyForm Noncommercial License 1.0.0 to keep the focus on education and nonprofit use.

---

## Architectural Evolution

### Phase 1: Monolithic foundation

The project began as a single-file Flask app focused on:
- Student and teacher account management
- Basic attendance and token earning
- Manual transactions
- Simple store items

### Phase 2: Blueprint refactor

The application moved to a Blueprint-based architecture with modular routes, utilities, and templates. This improved maintainability, testability, and parallel development.

### Phase 3: Feature expansion

The platform grew into a complete classroom economy system:
- Payroll, rent, insurance, and banking
- Store items with pricing tiers, bundles, and expirations
- Hall passes and attendance tracking
- Student-to-student transfers
- CSV roster uploads and join-code claiming
- System admin tooling and logs

### Phase 4: Multi-tenancy and class isolation

A major initiative introduced a multi-teacher ownership model:
- StudentTeacher relationship table for shared students
- TeacherBlock for join-code roster seats
- Scoped helper queries in auth utilities
- Session-aware join_code isolation

The same-teacher multi-period data leak was resolved by adding join_code scoping to transactions and related models. See `../security/CRITICAL_SAME_TEACHER_LEAK.md` for historical detail and the resolution notes.

### Phase 5: Security and platform hardening

Security audits and reliability improvements expanded across the stack:
- Passkey authentication and encrypted TOTP secrets
- Rate limits for login and admin endpoints
- Expanded error logging and user reporting
- Network activity reporting and system admin tooling
- Ongoing deprecation cleanup for SQLAlchemy and datetime APIs

### Phase 6: Documentation and operational maturity

By v1.6.0, the documentation structure was consolidated, the roadmap was formalized, and operational runbooks were expanded for audits, migrations, and deployments.

---

## Key Technical Milestones

### Database evolution

The schema evolved from a handful of core tables into a full classroom economy model with tenancy-aware relationships and audit trails.

Migration count: 101

### Testing infrastructure

- 61 pytest files covering admin, student, financial flows, and multi-tenancy
- In-memory SQLite testing with foreign key enforcement
- Regression tests added for tenant scoping and critical fixes

### Deployment evolution

- Development: local Flask server
- Staging: PostgreSQL with CI/CD pipelines
- Production: DigitalOcean, Gunicorn, Redis, Cloudflare, and UptimeRobot monitoring

---

## Notable Fixes and Improvements

### Join code system overhaul

Join codes were hardened with collision detection, atomic claiming, and constraints. See `../archive/JOIN_CODE_FIX_SUMMARY.md`.

### Migration chain consolidation

A systematic merge strategy and validation checks prevent multiple Alembic heads. See `../development/MIGRATION_GUIDE.md`.

### Duplicate data cleanup

Cleanup scripts were created to resolve legacy duplicate students, with dry-run support and logging.

### Timezone handling

UTC storage with user-timezone conversion is now standard. See `../technical-reference/TIMEZONE_HANDLING.md`.

### Deprecated pattern cleanup

Ongoing refactors replace deprecated SQLAlchemy and datetime patterns to keep the codebase modern and warning-free.

---

## Current Status and Roadmap

- Version 1.0.0 released: 2024-11-29
- Current version: 1.6.0
- Target version: 1.7.0

Active priorities and roadmap details live in:
- `../development/DEVELOPMENT.md`
- `../project/ROADMAP_v1.6.0.md`

---

## Community and Collaboration

### AI-assisted development

Canonical contributor guidance for AI tools is in `../../CLAUDE.md`, with a project-specific summary in `../ai/CLAUDE.md`.

### Open source but noncommercial

Contributions are welcome under the noncommercial license. See `../../CONTRIBUTING.md` for guidelines.

---

## Conclusion

Classroom Token Hub has progressed from a small classroom prototype to a secure, multi-tenant platform that supports rich financial learning experiences. The project continues to focus on correctness, privacy, and teacher control as it evolves.

For detailed technical history, see:
- `../archive/` for historical bug fixes and feature summaries
- `../CHANGELOG.md` for release history
- `../security/` for security audit reports
- `../operations/` for deployment and operational guides
