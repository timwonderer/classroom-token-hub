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
2. Use the [Student Diagnostics Index](user-guides/diagnostics/student.md) or [Teacher Diagnostics Index](user-guides/diagnostics/teacher.md) for fast answers.
3. Skim the [Architecture Guide](technical-reference/architecture.md) for system structure and security notes.
4. If you are operating the app, keep the [Deployment Guide](operations/Deployment_Guide.md) and [Operations README](operations/README.md) handy.

---

## Documentation Map

### Diagnostics (Fast Answers)
- **[Student Diagnostics Index](user-guides/diagnostics/student.md)** - Login, classes, attendance, money, store, rent, hall passes.
- **[Teacher Diagnostics Index](user-guides/diagnostics/teacher.md)** - Feature settings, students, payroll, store, rent, announcements.
- **[Classroom Economy Guide](user-guides/economy_guide.md)** - Pricing ranges and balance checks.

### Feature Guides (Structured by Role)
- **[Teacher Feature Guides](user-guides/features/teacher/index.md)** - Classroom, economy, bills, and settings in focused pages.
- **[Student Feature Guides](user-guides/features/student/index.md)** - Account, work, store, bills, and support in focused pages.

### Quick References
- **[Architecture Guide](technical-reference/architecture.md)** - Stack, project layout, patterns, and security posture.
- **[Database Schema](technical-reference/database_schema.md)** - Current models and relationships.
- **[API Reference](technical-reference/api_reference.md)** - REST endpoints and authentication expectations.
- **[Analytics Specification](technical-reference/analytics-specification.md)** - System health observability and analytics dashboard.
- **[Economy Specification](technical-reference/economy-specification.md)** - Developer-only ratios and balancing rules.
- **[Timezone Handling](technical-reference/TIMEZONE_HANDLING.md)** - UTC storage and conversion patterns.

### Deployment & Operations
- **[Deployment Guide](operations/Deployment_Guide.md)** - Environment variables, CI/CD references, and production checklist.
- **[Operations README](operations/README.md)** - Cleanup, demo session hygiene, and PII audit procedures.
- **[Multi-Tenancy Fix Deployment](operations/MULTI_TENANCY_FIX_DEPLOYMENT.md)** - Deployment procedures for multi-tenancy fixes.
- **[Changelog](../CHANGELOG.md)** - Notable changes and release notes.

### Releases
- **[Changelog](../CHANGELOG.md)** - All release notes and version history are maintained in the main changelog.

---

## Common Questions
- **Why can't I log in?** -> [Student Login Diagnostics](user-guides/diagnostics/student-login.md)
- **Why can't students claim accounts?** -> [Teacher Students Diagnostics](user-guides/diagnostics/teacher-students.md)
- **Why didn't payroll run?** -> [Teacher Payroll Diagnostics](user-guides/diagnostics/teacher-attendance-payroll.md)
- **Where are the feature guides?** -> [Teacher Feature Guides](user-guides/features/teacher/index.md)
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
| [Student Diagnostics Index](user-guides/diagnostics/student.md) | Students | Fast diagnostic entry point | 2026-01-03 |
| [Teacher Diagnostics Index](user-guides/diagnostics/teacher.md) | Teachers | Fast diagnostic entry point | 2026-01-03 |
| [Teacher Feature Guides](user-guides/features/teacher/index.md) | Teachers | Structured feature documentation | 2026-02-09 |
| [Student Feature Guides](user-guides/features/student/index.md) | Students | Structured feature documentation | 2026-02-09 |
| [Architecture Guide](technical-reference/architecture.md) | Developers | System architecture and patterns | 2025-11-23 |
| [Database Schema](technical-reference/database_schema.md) | Developers | Current models and relationships | 2025-11-23 |
| [API Reference](technical-reference/api_reference.md) | Developers | REST API documentation | 2025-11-23 |
| [Analytics Specification](technical-reference/analytics-specification.md) | Developers | Analytics dashboard and metrics | 2026-01-09 |
| [Classroom Economy Guide](user-guides/economy_guide.md) | Teachers | Economy ranges and balance checks | 2025-12-28 |
| [Deployment Guide](operations/Deployment_Guide.md) | DevOps | Deployment instructions | 2025-11-25 |
| [Economy Specification](technical-reference/economy-specification.md) | Developers | Financial system spec | 2025-12-11 |
| [Changelog](../CHANGELOG.md) | All | Version history and changes | 2026-02-09 |
| [README](../README.md) | All | Project overview and quick start | 2025-12-21 |

---
