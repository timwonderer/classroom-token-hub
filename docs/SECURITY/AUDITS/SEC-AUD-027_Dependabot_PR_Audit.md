# SEC-AUD-027: Dependabot PR Audit & Risk Report

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SEC-AUD-027      | 1.0     | 2026-04-27     | N/A        | Informative     |

---

## I. Overview

This report summarizes the outstanding Dependabot PRs and categorizes them by safety for merging into the `main` branch.

## II. Summary Table

| PR # | Package(s) | Version Change | Safety | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **1170** | `packaging` | 25.0 -> 26.1 | ✅ **Safe** | Merged into combo branch. |
| **1174** | `patch-updates` group | Various (Patch) | ✅ **Resolved** | Conflict fixed manually. See details below. |
| **1150** | `gevent` | 24.11.1 -> 26.4.0 | ⛔ **Unsafe** | Major bump. Risky for concurrency logic. |
| **1149** | `zope-interface` | 7.2 -> 8.3 | ⛔ **Unsafe** | Major bump. Foundational interface logic. |
| **1145** | `actions/github-script` | 8 -> 9 | ⛔ **Unsafe** | **Breaking changes** in script execution. |

---

## III. Detailed Risk Analysis

### PR #1174: Patch Updates Group (Resolved)
**Risk Level**: ~~High (Dependency Conflict)~~ → **Resolved**
**Updates**: `click`, `mako`, `psycopg2-binary`, `opentelemetry-api/sdk/exporter`.
**Root Cause**:
- Dependabot's `patch-updates` group did not recognize the instrumentation pre-release bump (`0.62b0 → 0.62b1`) as a patch update, leaving the instrumentation packages out of the group.
- This caused `opentelemetry-sdk 1.41.1` (requires `semantic-conventions==0.62b1`) to conflict with `opentelemetry-instrumentation-flask 0.62b0` (requires `semantic-conventions==0.62b0`).
**Resolution** (applied 2026-04-27 on `dependabot-combo-safe-updates`):
- `requirements.txt`: All OTel packages bumped in lockstep to `1.41.1` / `0.62b1`. `opentelemetry-semantic-conventions==0.62b1` explicitly pinned (was previously unpinned).
- `.github/dependabot.yml`: Added dedicated `opentelemetry` group (minor + patch) ahead of the catch-all group so core and instrumentation packages are always co-bumped in future PRs.

### PR #1145: actions/github-script (Unsafe)
**Risk Level**: High (Breaking Changes)
**Update**: 8 -> 9 (Major)
**Risk**:
- Version 9 of `actions/github-script` is ESM-only and **removes support for `require('@actions/github')`**.
- This repository uses `github-script` in `schema-gate.yml` and `check-migrations.yml`.
- While the scripts don't currently use `require`, the move to ESM-only and the injection of `getOctokit` requires careful manual validation of the existing workflow scripts.
- **Recommendation**: Manually update the workflows to v9 and verify in a test PR before merging.

### PR #1150: gevent (Unsafe)
**Risk Level**: Medium (Major Bump)
**Update**: 24.11.1 -> 26.4.0 (Major)
**Risk**:
- `gevent` is a core concurrency library that uses monkeypatching.
- A jump from 24 to 26 spans several years of changes and internal adjustments to `greenlet` and signal handling.
- Major version bumps in `gevent` have historically caused subtle async regressions in Flask/Gunicorn environments.
- **Recommendation**: Perform a soak test in a staging environment before upgrading.

### PR #1149: zope-interface (Unsafe)
**Risk Level**: Medium (Major Bump)
**Update**: 7.2 -> 8.3 (Major)
**Risk**:
- Foundational library for `gevent` and other async tools.
- Major version change (7 -> 8) may include breaking changes in how interfaces are defined or validated.
- **Recommendation**: Coordinate this update with the `gevent` upgrade.

---

## IV. Combo Merge Status

A new branch `dependabot-combo-safe-updates` has been created.
- **Included**: PR #1170 (`packaging`), OpenTelemetry lockstep upgrade (manual fix for PR #1174 conflict).
- **Excluded**: PR #1145, #1149, #1150 due to identified risks.

**Verification**:
- Local tests (`pytest`) were run. The pre-existing `psycopg2.errors.DependentObjectsStillExist` DB teardown error (present on `main`) was resolved in this PR by replacing `db.drop_all()` with `DROP SCHEMA public CASCADE` in `tests/conftest.py`.
- `pip install -r requirements.txt --dry-run` confirms clean dependency resolution. `opentelemetry-semantic-conventions==0.62b1` is now the sole required version across all OTel packages.
