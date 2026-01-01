# Release Notes - Version 1.6.0

**Release Date**: January 1, 2026  
**Focus**: Repository organization, multi-tenancy fixes, and operational stability

---

## Highlights

- Consolidated duplicate files and improved repository organization
- Fixed critical multi-tenancy violations in HallPassSettings
- Improved passkey authentication reliability with environment variable loading fixes
- Standardized file paths and references across all documentation
- Enhanced deployment reliability with verification steps

---

## Repository Organization

### File Consolidation
- Removed duplicate root-level scripts that existed in scripts/ directory
  - `seed_dummy_students.py`
  - `create_admin.py`
  - `add_join_code_column.py`
  - `check_syntax.py`
  - `cleanup_invite_codes.py`
  - `generate_revision_id.py`
  - `manage_invites.py`
- Removed duplicate nginx configuration file from root (kept in deploy/nginx/)
- Removed duplicate student_upload_template.csv from app/resources/ (kept in root where code references it)

### Documentation Updates
- Updated all documentation to reference scripts/ directory for utility scripts
- Standardized file path references across README, architecture docs, and operations guides
- Fixed inconsistent paths for student upload template
- Updated setup_jules.sh to use correct script paths

---

## Bug Fixes

### Multi-Tenancy Violation
Fixed critical bug where `HallPassSettings` records were created without `teacher_id`, violating NOT NULL constraint and breaking multi-tenancy isolation.

**Impact**: This could cause hall pass settings to be shared across teachers or fail to create entirely.

**Resolution**:
- Fixed `/api/hall-pass/settings` endpoint to scope settings by `teacher_id` from session
- Fixed hall pass creation in `/tap` endpoint to retrieve `teacher_id` from `join_code` via `TeacherBlock` lookup
- All `HallPassSettings` queries now properly scoped by `teacher_id` and `block`

**Files Changed**: `app/routes/api.py`, `app/routes/admin.py`

### Passkey Authentication

#### Environment Variable Loading
Fixed environment variables not loading in production deployments, causing passkey authentication to fail.

**Impact**: Passwordless.dev API keys were not being loaded when running under gunicorn, breaking passkey authentication.

**Resolution**: Specified explicit path to `.env` file in `load_dotenv()` call to ensure environment is loaded regardless of gunicorn working directory.

**Files Changed**: `app/__init__.py`

#### Token Destructuring
Fixed token destructuring in `signinWithDiscoverable()` to properly handle error responses from passwordless.dev SDK.

**Impact**: Error responses from failed passkey authentication attempts were not being properly caught, leading to unclear error messages.

**Resolution**: Updated destructuring pattern to handle both success and error responses from passwordless.dev.

**Files Changed**: `templates/sysadmin_login.html`, `templates/admin_login.html`

### Content Security Policy
Restored `'unsafe-eval'` directive to `script-src` CSP policy as it is required by passwordless.dev library's minified build.

**Context**: The passwordless.dev library uses `new Function()` internally in its minified build, which requires `unsafe-eval`. This was temporarily removed in v1.5.0 but needs to be present for passkey authentication to function.

**Files Changed**: `app/__init__.py`

### Deployment Verification
Added verification steps to confirm environment variables are properly written to `.env` and loaded by systemd service.

**Files Changed**: Deployment documentation

---

## Changes

### File Organization
- Consolidated duplicate scripts into scripts/ directory
- Removed obsolete root-level duplicates
- Standardized all script references in documentation to use scripts/ prefix

### Path Consistency
- Fixed inconsistent references to student_upload_template.csv
- Updated all documentation to reference correct file paths
- Improved setup script reliability

---

## Documentation

### Improved Organization
- Better repository structure with clear separation of concerns
- Removed confusing duplicate files that could lead to maintenance errors
- Clearer documentation paths and references

### Updated References
- All script references now point to scripts/ directory
- Student upload template references standardized
- Setup and deployment guides updated with correct paths

---

## Version Information

### Updated Versions
- README.md: Updated to v1.6.0
- DEVELOPMENT.md: Updated to v1.6.0, target v1.7.0
- CHANGELOG.md: Added v1.6.0 release entry

### Recent Releases Timeline
- v1.6.0 (January 1, 2026) - Repository organization and stability
- v1.5.0 (December 29, 2025) - Issue reporting and resolution system
- v1.4.0 (December 27, 2025) - Announcements and UI/UX improvements
- v1.3.0 (December 25, 2025) - Passwordless authentication

---

## Developer Notes

### File Paths
Going forward, all utility scripts should be run from the scripts/ directory:
```bash
python scripts/seed_dummy_students.py
python scripts/create_admin.py
```

### Template Files
The student upload template remains at root level (`student_upload_template.csv`) as the code references this location. Documentation has been updated to reflect this.

### Configuration Files
Deployment configuration files are now properly organized in the deploy/ directory structure.

---

## Upgrade Path from v1.5.0

### No Database Changes
This release does not include any database migrations. Upgrade is straightforward:

1. Pull latest code
2. Restart application server
3. Verify environment variables are loaded (passkey authentication)
4. Update any custom scripts that referenced root-level utilities

### Breaking Changes
None. This is a maintenance release with no breaking changes to functionality.

---

## Known Issues

None identified at time of release.

---

## Contributors

Thank you to everyone who contributed to this release through code, testing, and feedback.

---

## Next Steps

See [DEVELOPMENT.md](../../development/DEVELOPMENT.md) for the roadmap toward v1.7.0, which will focus on:
- Completing collective goals feature in store system
- Enhanced analytics and reporting
- Continued security hardening
- Performance optimizations
