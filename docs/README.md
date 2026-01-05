---
title: Documentation Home
description: Complete guide to using Classroom Token Hub - feature guides, troubleshooting, and help resources.
keywords: [documentation, help, guide, tutorial, how-to, manual, support]
roles: [teacher, student]
---

# Classroom Token Hub - Documentation Index

Welcome to the Classroom Token Hub documentation. This index points you to fast, diagnostic answers first.

---

## Start Here

1. Review the [project README](../README.md) for a high-level overview and setup steps.
2. Use the [Student Diagnostics Index](diagnostics/student.md) or [Teacher Diagnostics Index](diagnostics/teacher.md) for fast answers.
3. Skim the [Architecture Guide](technical-reference/architecture.md) for system structure and security notes.
4. If you are operating the app, keep the [Deployment Guide](Deployment_Guide.md) and [Operations README](operations/README.md) handy.

---

## Documentation Map

### Diagnostics (Fast Answers)
- **[Student Diagnostics Index](diagnostics/student.md)** - Login, classes, attendance, money, store, rent, hall passes.
- **[Teacher Diagnostics Index](diagnostics/teacher.md)** - Feature settings, students, payroll, store, rent, announcements.
- **[Classroom Economy Guide](user-guides/economy_guide.md)** - Pricing ranges and balance checks.

### Quick References
- **[Architecture Guide](technical-reference/architecture.md)** - Stack, project layout, patterns, and security posture.
- **[Database Schema](technical-reference/database_schema.md)** - Current models and relationships.
- **[API Reference](technical-reference/api_reference.md)** - REST endpoints and authentication expectations.
- **[Economy Specification](technical-reference/ECONOMY_SPECIFICATION.md)** - Developer-only ratios and balancing rules.
- **[Timezone Handling](technical-reference/TIMEZONE_HANDLING.md)** - UTC storage and conversion patterns.

### Development
- **[Development Priorities](development/DEVELOPMENT.md)** - Current priorities, roadmap, and active tasks.
- **[Economy Balance Checker](development/ECONOMY_BALANCE_CHECKER.md)** - CWI implementation guide and API reference.
- **[Deprecated Code Patterns](development/DEPRECATED_CODE_PATTERNS.md)** - Code modernization tracking.
- **[System Admin Interface](development/SYSADMIN_INTERFACE_DESIGN.md)** - Sysadmin flows and UX principles.
- **[Migration Guide](development/MIGRATION_GUIDE.md)** - Alembic tips and conflict resolution.
- **[Jules Setup](development/JULES_SETUP.md)** - Development environment setup.
- **[Seeding Instructions](development/SEEDING_INSTRUCTIONS.md)** - Test data seeding procedures.
- **[Testing Summary](development/TESTING_SUMMARY.md)** - Test coverage and validation results.
- **[Migration Status](development/MIGRATION_STATUS_REPORT.md)** - Database migration status tracking.

### Project & Planning
- **[Project History](project/PROJECT_HISTORY.md)** - Philosophy, evolution, and milestone context.
- **[Implementation Progress](project/IMPLEMENTATION_PROGRESS.md)** - Feature-by-feature delivery tracking.

### Deployment & Operations
- **[Deployment Guide](Deployment_Guide.md)** - Environment variables, CI/CD references, and production checklist.
- **[Operations README](operations/README.md)** - Cleanup, demo session hygiene, and PII audit procedures.
- **[Multi-Tenancy Fix Deployment](operations/MULTI_TENANCY_FIX_DEPLOYMENT.md)** - Deployment procedures for multi-tenancy fixes.
- **[Changelog](CHANGELOG.md)** - Notable changes and release notes.

### Security
- **[Security Audit 2025](operations/SECURITY_AUDIT_2025.md)** - Comprehensive security audit findings.
- **[Multi-Tenancy Audit](security/MULTI_TENANCY_AUDIT.md)** - Multi-tenancy security analysis.
- **[Critical Same-Teacher Leak](security/CRITICAL_SAME_TEACHER_LEAK.md)** - Resolved data isolation fix.
- **[Validation Report](security/VALIDATION_REPORT.md)** - Input/output validation audit.
- **[Access & Secrets Report](security/ACCESS_AND_SECRETS_REPORT.md)** - Access control and secrets review.
- **[Source Code Vulnerability Report](security/SOURCE_CODE_VULNERABILITY_REPORT.md)** - Code security analysis.
- **[Network Vulnerability Report](security/NETWORK_VULNERABILITY_REPORT.md)** - Network security assessment.

### Archive & Releases
- **[Release Notes v1.4.0](archive/releases/RELEASE_NOTES_v1.4.0.md)** - Announcement system, UI/UX enhancements, security fixes (Dec 27, 2025)
- **[Release Notes v1.3.0](archive/releases/RELEASE_NOTES_v1.3.0.md)** - Passwordless authentication, encrypted TOTP, security audit (Dec 25, 2025)
- **[Release Notes v1.2.1](archive/releases/RELEASE_NOTES_v1.2.1.md)** - Migration hardening, join code audits (Dec 21, 2025)
- **[Release Notes v1.2.0](archive/releases/RELEASE_NOTES_v1.2.0.md)** - Progressive Web App, accessibility (Dec 18, 2025)
- **[Release Notes v1.1.1](archive/releases/RELEASE_NOTES_v1.1.1.md)** - Stability patch (Dec 15, 2025)
- **[Release Notes v1.1.0](archive/releases/RELEASE_NOTES_v1.1.0.md)** - Dashboard analytics and UI redesign (Dec 13, 2024)
- **[Release Notes v1.0.0](archive/releases/RELEASE_NOTES_v1.0.md)** - First stable release (Nov 29, 2024)
- **[Archived Fix Reports](archive/README.md)** - Historical bug fix and feature implementation summaries.

---

## Common Questions
- **Why can't I log in?** -> [Student Login Diagnostics](diagnostics/student-login.md)
- **Why can't students claim accounts?** -> [Teacher Students Diagnostics](diagnostics/teacher-students.md)
- **Why didn't payroll run?** -> [Teacher Payroll Diagnostics](diagnostics/teacher-attendance-payroll.md)
- **What's the database structure?** -> [Database Schema](technical-reference/database_schema.md)
- **How does the economy system work?** -> [Classroom Economy Guide](user-guides/economy_guide.md)

---

## Documentation Standards

- Prefer diagnostic checklists over long explanations.
- Keep each doc focused on a single feature or route.
- Use "If X happened, check these" and "This is expected when" sections.
- Update relevant docs with every feature, schema, or operational change.

---

## Last Updated Snapshots

| Document | Audience | Purpose | Last Updated |
|----------|----------|---------|--------------|
| [Student Diagnostics Index](diagnostics/student.md) | Students | Fast diagnostic entry point | 2026-01-03 |
| [Teacher Diagnostics Index](diagnostics/teacher.md) | Teachers | Fast diagnostic entry point | 2026-01-03 |
| [Architecture Guide](technical-reference/architecture.md) | Developers | System architecture and patterns | 2025-11-23 |
| [Database Schema](technical-reference/database_schema.md) | Developers | Current models and relationships | 2025-11-23 |
| [API Reference](technical-reference/api_reference.md) | Developers | REST API documentation | 2025-11-23 |
| [Classroom Economy Guide](user-guides/economy_guide.md) | Teachers | Economy ranges and balance checks | 2025-12-28 |
| [Deployment Guide](Deployment_Guide.md) | DevOps | Deployment instructions | 2025-11-25 |
| [Economy Specification](technical-reference/ECONOMY_SPECIFICATION.md) | Developers | Financial system spec | 2025-12-11 |
| [Changelog](../CHANGELOG.md) | All | Version history and changes | 2025-12-27 |
| [README](../README.md) | All | Project overview and quick start | 2025-12-21 |

---
