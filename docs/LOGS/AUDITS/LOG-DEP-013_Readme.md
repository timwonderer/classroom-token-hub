# Operations Documentation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DEP-013| 1.1 | 2026-03-08 | 1.0 |Normative|

This directory contains operational guides and troubleshooting documentation for managing the Classroom Token Hub in production.

## Available Guides

### [Cleanup Duplicate Students](LOG-DEP-002_Cleanup_Duplicates.md)

Guide for identifying and safely removing duplicate student records that may have been created due to roster upload issues.

**Use this when:**

- You notice duplicate students in the system
- Students appear multiple times in different blocks
- After fixing a roster upload bug

**Key features:**

- Uses Flask script to properly handle encrypted fields
- Preserves all transaction history and related data
- Safe migration of data from duplicates to primary records
- Preview mode to see what will happen before making changes

### [Demo Session Lifecycle and Cleanup](../../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-004_Demo_Sessions.md)

How to monitor and clean demo student sessions that power the admin "view as student" experience.

**Use this when:**

- You need to verify demo sessions are expiring after the 10-minute limit
- An expired demo student remains visible in the admin UI
- The background cleanup job is paused or failing

**Key features:**

- Documents automatic cleanup paths (logout, scheduled job, route guard)
- Provides a manual cleanup snippet using `cleanup_demo_student_data`
- Notes the foreign-key-safe deletion order and required transaction commit

### [Public Demo Environment (Teacher + Student)](../../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-003_Demo_Env_Setup.md)

How to stand up the landing-page demo endpoints (teacher and student) using the built-in demo session lifecycle and seeded data.

**Use this when:**

- You need the `docs/index.html` demo iframes/buttons to point at a live demo
- Standing up a separate demo deployment that is isolated from production data
- Creating disposable demo student sessions for public previews

**Key features:**

- Reuses `create_demo_student` and the 10-minute auto-cleanup pipeline
- References existing scheduler job and schema
- Provides curl example to mint a demo session URL for embedding

### [Pulsetic Monitoring Setup](../../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-012_Pulsetic_Setup.md)

Complete guide for setting up UptimeRobot monitoring and creating a public status page.

**Use this when:**

- Setting up uptime monitoring for production
- Creating a public status page for users
- Configuring maintenance windows
- Troubleshooting monitoring issues

**Key features:**

- Health endpoint configuration (`/health`, `/health/deep`)
- Public status page setup
- Firewall configuration for UptimeRobot IPs
- Alert contact configuration

### [DigitalOcean & Cloudflare Setup](../../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-005_Digitalocean_Cloudflare_Setup.md)

Infrastructure setup guide for production deployment.

**Use this when:**

- Setting up production infrastructure
- Configuring firewall rules
- Managing Cloudflare proxy settings

## Adding New Operational Guides

When creating new operational documentation:

1. **Create a descriptive filename** (e.g., `RESET_DATABASE.md`, `BACKUP_RESTORE.md`)
2. **Include these sections:**
   - Problem/Situation description
   - Prerequisites/Requirements
   - Step-by-step instructions
   - Safety warnings
   - Verification steps
   - Rollback procedures (if applicable)
3. **Update this README** with a link and description
4. **Cross-reference** from relevant technical documentation

## Related Documentation

- **[Deployment Guide](../../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-006_Deployment_Guide.md)** - Initial setup and deployment procedures
- **[Migration Specifications](../../STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-011_Migration_Specifications.md)** - Database schema migrations
- **[System Admin Design](../../ARCHITECTURE/SYSADMIN/ARC-SYS-001_Sysadmin_Interface.md)** - Admin interface features

## Emergency Procedures

For critical issues:

1. Check the relevant operational guide in this directory
2. Review error logs via the System Admin portal
3. Consult the [Teacher Diagnostics Index](../../user-guides/diagnostics/teacher.md) for troubleshooting checklists
4. Review recent changes in [CHANGELOG.md](../RELEASES/LOG-REL-002_Changelog_Mirror.md)

---

**Last Updated:** 2026-02-09
**Maintained by:** Project maintainers and operations team
