---
title: Self-hosting Classroom Token Hub
category: self-hosting
description: Deployment boundaries and evidence required to operate a private Classroom Token Hub instance.
roles: [operator]
keywords: [self-hosting, deployment, configuration, backups, operations]
---

# Self-hosting Classroom Token Hub

This page is an orientation document for an operator running a private v2
instance. It is not a substitute for the normative deployment and security
documents linked below.

## Before you deploy

- Read the [v2 production transition runbook](../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-023_V2_Production_Transition_Runbook.md).
- Use the [live-test runbook](../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-022_V2_Live_Test_Runbook.md) for controlled verification.
- Review [SOP-SEC-001](../STANDARD_OPERATING_PROCEDURES/SECURITY/SOP-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_OPERATIONS.md) and the canonical environment/key requirements before supplying secrets.
- Confirm the target database, service identity, revision, and backup plan before any migration or reset.

## Runtime boundaries

Classroom state is class-scoped and must be accessed through the canonical
context pipeline. Do not bypass the application with ad-hoc writes to ledger,
obligation, entitlement, or policy tables. State-changing behavior belongs to
the owning FEAT and must carry its required idempotency and audit evidence.

The application is not an offline data store. The service worker deliberately
keeps authenticated routes network-only so one class's live data cannot be
served to another class from a stale cache.

## Configuration and secrets

Set environment variable names from the deployment and security specifications
for the target environment. Never copy secret values into the repository,
documentation, logs, screenshots, or issue reports. Keep lookup peppers,
encryption keys, session secrets, audit keys, and database credentials in
separate secret lifecycles as specified by the security contracts.

## Operational evidence

A successful setup command is not deployment or launch certification. Record,
at minimum, the deployed revision, migration result, health checks, integration
configuration checks, backup/restore evidence, and the controlled browser test
result. Use the public status service and the application's bounded health
routes according to the production runbook.

## Recovery and rollback

Follow the runbook for rollback and database recovery. Do not infer database
safety from a database name, and do not delete or reset a target until its exact
host, service relationship, revision, owner, and backup state have been
verified.

## Related normative documents

- [Canonical invariants](../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md)
- [Domain authority summary](../DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md)
- [Feature execution directive](../FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md)
- [Documentation standard](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md)
