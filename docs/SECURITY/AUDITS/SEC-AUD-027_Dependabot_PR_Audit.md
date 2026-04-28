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
| **1174** | `patch-updates` group | Various (Patch) | ⚠️ **Unsafe** | **Conflict detected.** See details below. |
| **1150** | `gevent` | 24.11.1 -> 26.4.0 | ⛔ **Unsafe** | Major bump. Risky for concurrency logic. |
| **1149** | `zope-interface` | 7.2 -> 8.3 | ⛔ **Unsafe** | Major bump. Foundational interface logic. |
| **1145** | `actions/github-script` | 8 -> 9 | ⛔ **Unsafe** | **Breaking changes** in script execution. |

---

## III. Detailed Risk Analysis

### PR #1174: Patch Updates Group (Unsafe As-Is)
**Risk Level**: High (Dependency Conflict)
**Updates**: `click`, `mako`, `psycopg2-binary`, `opentelemetry-api/sdk/exporter`.
**Risk**:
- Attempting to merge this PR results in a **Dependency Resolution Failure**.
- `opentelemetry-sdk 1.41.1` (proposed) requires `opentelemetry-semantic-conventions==0.62b1`.
- However, the repository has `opentelemetry-instrumentation-flask` pinned to `0.62b0`, which strictly requires `opentelemetry-semantic-conventions==0.62b0`.
- **Recommendation**: This PR should be recreated or updated to include the `opentelemetry-instrumentation-*` packages in the update group to ensure version alignment.

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
- **Included**: PR #1170 (`packaging`).
- **Excluded**: All others due to identified risks.

**Verification**:
- Local tests (`pytest`) were run. While errors were detected in the database setup (`psycopg2.errors.DependentObjectsStillExist`), these were confirmed to be **pre-existing** on the `main` branch and unrelated to the `packaging` update.
