---
title: Classroom Token Hub — Self-Hosting Handbook
category: self-hosting
description: Deployment boundaries and evidence required to operate a private Classroom Token Hub instance.
roles: [operator]
keywords: [self-hosting, deployment, configuration, backups, operations]
---

# Classroom Token Hub — Self-Hosting Handbook

This handbook is for the operator who controls a private CTH installation, its host, DNS, HTTPS admission policy, keys, backups and authorized accounts. The operator can be one person. CTH is distributed under the PolyForm Noncommercial License 1.0.0. Review `LICENSE` in the selected release before use or redistribution and retain the required notices. [License terms](https://github.com/timwonderer/classroom-token-hub/blob/main/LICENSE)

## Start here

| When | Chapter |
| --- | --- |
| Before creating a host | [Reference profile, prerequisites, costs and ten installation stages](reference-installation.md) |
| Before starting services | [Configuration and secret inventory](configuration.md) |
| When installing a new database | [Release-specific database baseline, verification and recovery](fresh-database.md) |
| After the readiness check | [First authorized use, acceptance, maintenance, recovery and decommissioning](operations.md) |
| When running an attended rehearsal | [Manual dispatch, exact-ID cleanup and owner confirmation](staging-controller.md) |
| When preparing the staging guest | [Release bundle, guest identity, connector and per-run credentials](staging-bootstrap.md) |
| When authorizing the first cloud rehearsal | [Phase C execution plan and resource ownership review](phase-c.md) |

**Evidence status.** The reference-host procedure is **proposed**. **Locally tested** applies only to the checks whose results are recorded for the selected release. B1 demonstrated database equivalence, a genuine successor upgrade, protected audit verification and CLI-only sysadmin bootstrap. **Reference-host tested** requires a successful run on the specified Ubuntu host. **Independently verified** additionally requires a second operator to complete the handbook from scratch without undocumented assistance. The latter two checks are pending.

## Before you deploy

- Read the [production release runbook](../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-002_Production_Transition_Runbook.md).
- Use the [live-test runbook](../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-001_Live_Test_Runbook.md) for controlled verification.
- Review [SOP-SEC-001](../STANDARD_OPERATING_PROCEDURES/SECURITY/SOP-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_OPERATIONS.md) and the canonical environment/key requirements before supplying secrets.
- Confirm the target database, service identity, revision, and backup plan before any migration or reset. For a new PostgreSQL database, use the [release-specific installation and verification procedure](fresh-database.md).

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

## Installation and integration boundaries

| What you are checking | Dependencies and evidence |
| --- | --- |
| Core application health | Run the selected application revision with PostgreSQL and its supported schema. Startup requires `DATABASE_URL`, `FLASK_ENV`, `SECRET_KEY`, `ENCRYPTION_KEY`, `PEPPER_KEY` and `AUDIT_HMAC_KEY`. A successful `/health` executes `SELECT 1`. On `/health/status`, only the database signal executes a check. Unregistered checks remain unknown. Neither endpoint requires a separate status publisher. |
| Production security and functional acceptance | Serve HTTPS through restricted ingress. Production startup additionally requires a Turnstile site/secret pair registered for the deployment hostname. Configure a shared rate-limit store (`RATELIMIT_STORAGE_URI` or `REDIS_URL`) and dedicated memory-only `STUDENT_SETUP_REDIS_URL` for claiming and recovery. That Redis instance must disable snapshots, AOF, replication and slow logging. Exercise Passwordless enrollment and sign-in with the deployment's `PASSWORDLESS_API_PUBLIC` and `PASSWORDLESS_API_KEY`. Configure a separate `CONFIGURATION_EXPORT_KEY` for signed configuration export/import. Record actual browser results under the [initial deployment browser procedure](../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-001A_Initial_Deployment_Browser_Validation.md). |
| Independently deployed monitoring and status | An operator can initialize and check the core without deploying the hosted status stack. Operators publishing equivalent status evidence must preserve its bounded, read-only observations, independent persistence and protected publication surface. A public status notice grants no authority over classroom data. See the [external persistence model](../SPEC/SPEC-OPS-002_EXTERNAL_STATUS_PERSISTENCE_MODEL.md) and [public request monitoring contract](../SPEC/SPEC-OPS-006_PUBLIC_REQUEST_MONITORING.md). |
| Full hosted-topology parity | Separately exercise restricted Cloudflare Access ingress, log ingestion into local Loki, the reduced telemetry sampler, gate-first collection, private collector invocation, Firestore persistence and the separate public and authenticated operator services. Record the target revision, observed source and timestamp for each check. A missing collector or inaccessible sample leaves that observation unknown. |

## Isolating a future staging deployment

The following configuration work is proposed. The current hosted defaults cannot
be used for an isolated parity run.

- **Collector targets.** Derive the fixed paths `/health/telemetry`, `/health/status`
  and `/static/manifest.json` from one explicitly approved staging HTTPS origin.
  All three currently point at the hosted application in `status_service/collector.py`.
  Preserve the no-redirect transport and gate-first check. Reject missing, malformed
  and production targets before any request. Check these refusals using local test
  destinations. Configure the host sampler against staging logs only.
- **Persistence and identity.** Set the collector and both status services to an
  explicit staging cloud project and Firestore database. The client currently infers
  its project from credentials and defaults the database to `cth-status-prod`.
  The hosted deployment workflow selects `cth-production-status`. Use identities
  scoped to staging and a separate scheduler target, operator allowlist, IAP audience
  and status session secret. Check the resolved project and database before writing.
- **Browser destinations.** The `STATUS_PAGE_URL` validator currently accepts only
  the hosted status origin and UptimeRobot. Configure an exact operator-approved
  HTTPS origin for staging, or omit the link. Replace the hard-coded hosted links
  on login, support, error and status pages before testing them. Set
  `MARKETING_SITE_URL` to staging for the home, privacy, terms and district
  redirects and review `EXTERNAL_DOCS_BASE_URL` and support destinations. Verify
  rendered links and redirect locations, including rejection of lookalike hosts.
- **Authentication and notifications.** Use staging-only provider accounts,
  domain registrations and callback origins. Route optional notification webhooks
  and any alert delivery to staging recipients only. Until those destinations and
  credentials have been isolated, leave the corresponding integration disabled
  and record the parity check as outstanding.

## Operational evidence

Record the deployed revision, database initialization or upgrade result, bounded
health observations, integration checks, backup/restore evidence and the controlled
browser test results. Record whether the run exercised core health, browser
acceptance or full hosted-topology parity. Independent verification additionally
requires a different operator to repeat the installation without undocumented help.

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
