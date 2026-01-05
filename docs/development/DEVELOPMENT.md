# Classroom Token Hub - Development Priorities

Last Updated: 2026-01-04
Current Version: 1.6.0
Target Version: 1.7.0

This document tracks active priorities and engineering standards. For release history, see [docs/CHANGELOG.md](../CHANGELOG.md). For detailed roadmap context and effort estimates, see [docs/project/ROADMAP_v1.6.0.md](../project/ROADMAP_v1.6.0.md).

## Current Focus (v1.7.0)

1. Complete collective goals for store items
   - Teacher UI for create/edit
   - Progress visibility and redemption flow
   - Notifications when goals are met
   - Documentation in student and teacher guides
   - Tests for teacher workflows

2. Analytics and reporting enhancements
   - Enhanced transaction reporting and filtering
   - Class economy health dashboard
   - Student progress reports (downloadable)
   - Attendance analytics improvements
   - Insurance and rent compliance reporting

3. Mobile experience polish
   - PWA performance improvements
   - Offline behavior polish
   - Touch-target and navigation refinements
   - Device matrix testing

4. Performance optimizations
   - Query profiling and tuning
   - Caching and asset optimization
   - Reduce page load times

## Platform Hardening (do not defer)

### Multi-teacher hardening
Status: In progress (scoped queries shipped)

Remaining tasks:
- Finalize migration to remove legacy students.teacher_id
- Publish runbook for NOT NULL enforcement and teacher reassignment
- Audit direct Student.query.get usage; replace with get_student_for_admin
- Add DB safeguard for ownership changes (define ON DELETE strategy)

### Shared-student test coverage
- Add payroll flow tests for shared students
- Add attendance flow tests for shared students
- Add regression test for student_teachers uniqueness constraint

### Operational safety documentation
- Runbook for schema changes affecting tenancy or payroll
- Pre/post checks for migrations with maintenance mode
- Migration validation checklist

## Deferred and Future Features (v1.8+)

### Jobs feature restoration
Summary: Rebuild the classroom jobs system removed in Dec 2025. Models, routes, forms, and tests exist in git history.

Scope:
- Restore models, routes, and forms from history
- Update for join_code scoping
- Rebuild tests and UI
- Add student job board and teacher analytics

See [docs/project/ROADMAP_v1.6.0.md](../project/ROADMAP_v1.6.0.md) for details and effort estimates.

### Custom condition builder
Summary: Visual rule builder for rent, insurance, store, payroll, and banking logic.

Phased approach:
- JSON rules engine and form builder
- Drag-and-drop UI
- Optional Blockly integration

### Teacher self-serve account recovery
Status: Deferred pending security and PII tradeoff decision.

Notes:
- Current workaround: sysadmin-assisted TOTP reset
- Evaluate recovery options (backup codes, recovery email, etc.) with security review

### Long-term roadmap (v2.0+)
- Internationalization (language and currency localization)
- Parent portal and curriculum resources

## Recent Releases (summary)

- v1.6.0: repository organization, multi-tenancy fixes for HallPassSettings, passkey reliability improvements
- v1.5.0: issue reporting and resolution system, attendance issue reporting, security hardening
- v1.4.0: announcement system, UI/UX redesign, accordion navigation, student dashboard improvements
- v1.3.0: passkey authentication and encrypted TOTP secrets, service worker improvements

## Multi-Tenancy Architecture

### Join code as source of truth
- Class isolation: join codes partition transactions and attendance by class period
- Student sessions persist current_join_code to scope balances and transactions
- student_teachers link table is authoritative for ownership
- students.teacher_id is deprecated for access control

### Access control
- Use scoped helpers: get_admin_student_query, get_student_for_admin (app/auth.py)
- Admin routes must use scoped helpers; avoid direct Student.query
- System admins have global visibility

### Database constraints
- student_teachers enforces (student_id, admin_id) uniqueness
- Cascading deletes configured through relationships
- Enforce join_code NOT NULL on ledger tables after backfill validation

## Code Quality Standards

### Authentication and authorization
- Prefer scoped helpers over ad-hoc filters
- Check is_system_admin for global access requirements
- Use @admin_required and @system_admin_required consistently

### Database best practices
- Migrations: sync with main before creating new migrations
- Queries: use scoped helpers for tenant-aware access
- Timestamps: use datetime.now(timezone.utc) instead of utcnow()
- Session access: use db.session.get(Model, id)

### Security guidelines
- Keep PII minimal (prefer non-PII identifiers)
- Validate all user input at the route level
- Use CSRF protection on all forms
- Encrypt sensitive data at rest
- Avoid debug print statements in production

### Testing requirements
- Run pytest -q before committing
- Add tests for new features and bug fixes
- Add tenancy coverage when changing scoping logic
- Ensure foreign key constraints enabled in tests

## Development Workflow

### Before creating migrations
Important: follow this workflow to prevent multiple heads.

1. Sync with latest code:
   ```bash
   git fetch origin main
   git merge origin/main
   ```

2. Verify exactly one migration head:
   ```bash
   flask db heads
   ```

3. If multiple heads exist, merge them first:
   ```bash
   flask db merge heads -m "Merge migration heads"
   ```

4. Check current revision:
   ```bash
   flask db current
   ```

5. Create migration:
   ```bash
   flask db migrate -m "Clear description"
   ```

6. Verify new migration:
   - Open generated file in migrations/versions/
   - Verify down_revision matches flask db current output
   - If mismatch, delete migration and restart workflow

7. Test migration:
   ```bash
   flask db upgrade
   flask db downgrade
   flask db upgrade
   ```

8. Quick verification:
   ```bash
   bash scripts/check-migration-heads.sh
   ```

### Before submitting PR
- Tests pass locally (pytest -q)
- Migrations reviewed for safety (lock impact, backfill steps)
- No new deprecation warnings
- Code follows project conventions
- Documentation updated where needed
- Commit messages are clear and descriptive

## Documentation Map

### User documentation
- [Student Diagnostics](../diagnostics/student.md)
- [Teacher Diagnostics](../diagnostics/teacher.md)

### Technical reference
- [Architecture](../technical-reference/architecture.md)
- [Database Schema](../technical-reference/database_schema.md)
- [API Reference](../technical-reference/api_reference.md)
- [Timezone Handling](../technical-reference/TIMEZONE_HANDLING.md)
- [Economy Specification](../technical-reference/ECONOMY_SPECIFICATION.md)

### Development guides
- [Economy Balance Checker](ECONOMY_BALANCE_CHECKER.md)
- [Migration Guide](MIGRATION_GUIDE.md)
- [Migration Best Practices](MIGRATION_BEST_PRACTICES.md)
- [Seeding Instructions](SEEDING_INSTRUCTIONS.md)
- [Deprecated Patterns](DEPRECATED_CODE_PATTERNS.md)
- [System Admin Design](SYSADMIN_INTERFACE_DESIGN.md)

### Operations and deployment
- [Deployment Guide](../Deployment_Guide.md)
- [Operations Guides](../operations/)
- [Security Audits](../security/)

### Historical reference
- [Project History](../project/PROJECT_HISTORY.md)
- [Changelog](../CHANGELOG.md)
- [Archive](../archive/)

## Getting Help

- Documentation index: [docs/README.md](../README.md)
- Technical questions: [Architecture Guide](../technical-reference/architecture.md)
- Security concerns: [Security Audits](../security/)
- Contributing: [CONTRIBUTING.md](../../CONTRIBUTING.md)
