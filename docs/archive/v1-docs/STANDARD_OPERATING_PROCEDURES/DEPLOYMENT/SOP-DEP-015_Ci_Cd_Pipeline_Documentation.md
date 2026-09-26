# CI/CD Pipeline Documentation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DEP-015| 1.1 | 2026-03-08 | 1.0 |Archived - non-normative|

> **Archived — history, not authority.** This document describes a superseded version of the system and is retained under `docs/archive/` as a record of what was once true. It governs nothing. Current authority lives in `docs/INVARIANT/`, `docs/DOMAIN/`, and `docs/STANDARD_OPERATING_PROCEDURES/`, in that order (`.claude/rules/documentation.md`).

## I. Purpose
Document the Continuous Integration and Continuous Deployment (CI/CD) pipelines, primarily configured via GitHub Actions, defining automated tests, staging deploy processes, and failure handling.

## II. Scope
All automated testing and deployment pipelines linked to the Classroom Token Hub main branch and active PRs.

## III. Authority Level
SOP Tier. Guides operational practice but cannot override ARC invariants.

## IV. Dependencies
- SOP-DEP-001: Production Deployment Instructions
- SOP-DEP-006: Deployment Guide

## V. Pipeline Configuration

### 1. Automated Testing
- All PRs targeting `main` must pass the `pytest` suite before merge.
- Coverage reports must be evaluated, specifically ensuring no missing test coverage on newly introduced routes.

### 2. GitHub Actions Workflows
- **Validation Workflow**: Runs unit and integration tests upon PR creation.
- **Deploy Workflow**: Triggered upon manual approval and merge to `main`. This connects to DigitalOcean instances or staging setups as configured.

### 3. Failure Handling & Notifications
- Failed checks block merge requests.
- Administrators are notified on workflow completion failures.
## VI. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.
