---
title: Phase C staging execution plan
category: self-hosting
description: Owner approval, reference configuration, acceptance and manual cleanup for one attended staging exercise.
roles: [operator]
---

# Phase C execution plan

**Proposed.** The first exercise establishes the Python 3.10 installation baseline. The owner approves one dispatch and personally destroys the identified Droplet and confirms its absence in DigitalOcean. B3 offline tests do not establish cloud or independent installation success.

For an owner-run console installation, use the [manual project procedure](staging-controller.md#rehearsal-with-one-digitalocean-team) in place of Actions dispatch and automated allocation. The installer, first-use checks and owner teardown are the same.

## Before approving the run

| Item | Owner check |
| --- | --- |
| Release | Record the reviewed workflow revision and exact application SHA. Use a reviewed application SHA containing the current proxied installer; the original B2 SHA predates this configuration. Record it for approval before allocation. Verify that its approved sources still offer the required Python 3.10 and PostgreSQL 14.24 packages. |
| Compute | One SFO3 Premium AMD Droplet, `s-2vcpu-4gb-amd`, 2 vCPUs, 4 GB RAM, 80 GB advertised local disk, Ubuntu 22.04 x86-64. Confirm the approved public image ID and provider quote. The controller rejects a quote above USD 0.05/hour. Use local PostgreSQL and two isolated Redis instances. |
| Time and cost | Plan 60–90 minutes, budget two hours for the exercise. At the selected USD 0.042/hour, two hours costs about USD 0.084 in compute. A Droplet left for 24 hours costs about USD 1.01 at that rate. Billing continues until destruction, including while powered off. The owner accepts delay if manual cleanup is needed. [Droplet billing](https://docs.digitalocean.com/products/droplets/details/pricing/) |
| Cloud and access | Verify the selected DigitalOcean team, separate staging project, VPC, network controls and the owner's console access. Confirm the previous exercise is clear. Review the inbound SSH path for the Actions runner, restricted HTTPS ingress, outbound routes and staging integration destinations. If using public management ingress, explicitly approve key-only TCP/22 on this temporary guest. Keep PostgreSQL, Redis and Gunicorn private. For manual proxied ingress admit origin TCP 443 only from the reviewed Cloudflare ranges. |
| Guest inputs | Prepare staging SSH, TLS and restricted ingress credentials, a dedicated hostname, and staging Turnstile and Passwordless registrations. Use fresh application keys, including the audit HMAC. Keep logs, Redis state, databases and any optional integration separate from production. Leave external status and notification paths disabled until their destinations are isolated. [Guest preparation](staging-bootstrap.md) |

## Acceptance and closeout

1. **Dispatch and identify the guest.** Follow the [attended workflow](staging-controller.md). Record the run link and returned numeric Droplet ID. Verify the SSH host identity in the authenticated provider console before releasing guest inputs. Stop on any mismatch.
2. **Install the reference release.** Check the canonical installer stage results, database revision, Redis isolation, Gunicorn and systemd readiness, single scheduler ownership and restricted TLS ingress. Record failures and skips explicitly.
3. **Exercise only approved scenarios.** For browser acceptance, test an admitted and denied session, two separately registered teachers, two owned economies, a shared fictional student and independent seat balances. Use supported claim, authentication and business workflows. Verify cross-class denial, student survival after one association disappears, final principal destruction, terminal class and teacher deletion and complete retained audit verification after a real financial transaction. Retain only bounded outcomes. Record outstanding scenarios when the run exercises installation alone. [Browser procedure](../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-001A_Initial_Deployment_Browser_Validation.md)
4. **Close the exercise personally.** Match the creation receipt with the staging project and provider activity. Personally destroy the exact temporary Droplet in the console and confirm absence, including after interrupted or failed runs. Check for separately billable volumes, snapshots, backups, reserved IPs, transfer or external services. Retire run-specific credentials and record the owner check and time. Keep the exercise open while ownership or absence is uncertain.
5. **Record what passed.** A successful maintainer installation supports the reference profile exercised. Independent verification requires another operator to repeat the handbook unaided. Python 3.14, rollback to 3.10, monitoring parity and any separate fault-injection rehearsal require their own approved scope and evidence.

## Preparation evidence — November 17, 2026

This records checks, not approval to allocate or proof of a deployed installation.

| Prerequisite | Observed result |
| --- | --- |
| Python and PostgreSQL | Read-only production package metadata reports Python 3.10.12 and PostgreSQL server/client 14.24. Both exact Ubuntu PostgreSQL `.deb` URLs returned HTTP 200. The fresh host must still verify its signed APT candidates before installation; no package changes were made to production. |
| Staging server certificate | Local public certificate metadata confirms `staging.classroomtokenhub.com`, issued by Let's Encrypt, valid through February 16, 2027. The certificate and private key match; the dedicated staging SSH key exists. No extra client certificate is needed by this profile. |
| Staging firewall | Provider read reports succeeded, HTTPS from the 15 reviewed Cloudflare IPv4 ranges, SSH from the enrolled owner address, unrestricted outbound, and no attached Droplet IDs. Tag visibility is not conclusive under the current scoped token; confirm actual attachment on the new guest. |
| DNS and Access | No staging A record returned in the public DNS check. Set it only after an approved guest has an IP. Owner previously reported an owner-only Access policy; admitted/denied browser behavior remains a live acceptance check. |
| Actions install inputs | Environment and repository input-name inventories contain no staging installation secrets. Actions is not prepared for dispatch. This is not a blocker for the manual rehearsal: prepare the private staging EnvironmentFile directly on the guest, as in production, and invoke the same handbook installer. Application credentials need not pass through GitHub. |
| Authentication and recovery | Staging Turnstile/Passwordless registration and private credential custody, encrypted backup destination and empty restore target still need confirmation. These are acceptance prerequisites, not reasons to create a tunnel, new domain, marketing site or monitoring stack. |
| Renewal parity | Production's Certbot timer is active/enabled. The temporary staging certificate was issued manually; automatic renewal is not established. Retire the temporary installation after the exercise. Long-lived operation needs verified renewal and reload before expiry. |

The controller and installer changes are governed by the infrastructure boundary in
[DOM-OPS-001](../DOMAIN/DOM-OPS-001_OPERATIONS_DOMAIN.md), credential isolation in
[SOP-SEC-001](../STANDARD_OPERATING_PROCEDURES/SECURITY/SOP-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_OPERATIONS.md),
and bounded validation claims in [INV-ARC-017](../INVARIANT/ARCHITECTURE/INV-ARC-017_GENERAL_TESTING_INVARIANTS.md).
No application FEAT, identity model, migration or audit contract changes are part of this correction.

Targeted verification for this correction:

- `python3.10 -m unittest discover -s infra/self-hosting -v`: 16 passed, including real loopback Nginx peer/Host rejection and local-health checks without client certificates.
- `python3.10 -m unittest discover -s infra/staging -q`: 23 passed against isolated fixtures and mocked provider responses; no cloud allocation.
- `python3.10 -m pytest --noconftest tests/test_self_hosting_handbook.py -q`: 2 passed.
- `actionlint .github/workflows/staging-ephemeral.yml` and `git diff --check`: passed.

These results do not establish live Access admission, a fresh Ubuntu installation,
provider enrollment, recovery acceptance or independent reproducibility.
