---
title: Phase C staging execution plan
category: self-hosting
description: Owner approval, reference configuration, acceptance and manual cleanup for one attended staging exercise.
roles: [operator]
---

# Phase C execution plan

**Proposed.** The first exercise establishes the Python 3.10 installation baseline. The owner approves one dispatch and personally confirms cleanup in DigitalOcean. B3 offline tests do not establish cloud or independent installation success.

## Before approving the run

| Item | Owner check |
| --- | --- |
| Release | Record the reviewed workflow revision and exact application SHA. The proposed first application is the committed B2 release `4427fd683475d56b0e5937e5cda93badff40c444`. Verify that its approved sources still offer the required Python 3.10 and PostgreSQL 14.24 packages. |
| Compute | One SFO3 Premium AMD Droplet, `s-2vcpu-4gb-amd`, 2 vCPUs, 4 GB RAM, 80 GB advertised local disk, Ubuntu 22.04 x86-64. Confirm the approved public image ID and provider quote. The controller rejects a quote above USD 0.05/hour. Use local PostgreSQL and two isolated Redis instances. |
| Time and cost | Plan 60–90 minutes, budget two hours for the exercise. At the selected USD 0.042/hour, two hours costs about USD 0.084 in compute. A Droplet left for 24 hours costs about USD 1.01 at that rate. Billing continues until destruction, including while powered off. The owner accepts delay if manual cleanup is needed. [Droplet billing](https://docs.digitalocean.com/products/droplets/details/pricing/) |
| Cloud and access | Verify the staging-only DigitalOcean identity, project, VPC, network controls and the owner's console access. Confirm the previous exercise is clear. Review the inbound SSH path for the Actions runner, restricted HTTPS ingress, outbound routes and staging-only destinations. If using public management ingress, explicitly approve key-only TCP/22 on this temporary guest. Keep PostgreSQL, Redis and origin ports private. |
| Guest inputs | Prepare staging SSH, TLS and restricted ingress credentials, a dedicated hostname, and staging Turnstile and Passwordless registrations. Use fresh application keys, including the audit HMAC. Keep logs, Redis state, databases and any optional integration separate from production. Leave external status and notification paths disabled until their destinations are isolated. [Guest preparation](staging-bootstrap.md) |

## Acceptance and closeout

1. **Dispatch and identify the guest.** Follow the [attended workflow](staging-controller.md). Record the run link and returned numeric Droplet ID. Verify the SSH host identity in the authenticated provider console before releasing guest inputs. Stop on any mismatch.
2. **Install the reference release.** Check the canonical installer stage results, database revision, Redis isolation, Gunicorn and systemd readiness, single scheduler ownership and restricted TLS ingress. Record failures and skips explicitly.
3. **Exercise only approved scenarios.** For browser acceptance, test an admitted and denied session, two separately registered teachers, two owned economies, a shared fictional student and independent seat balances. Use supported claim, authentication and business workflows. Verify cross-class denial, student survival after one association disappears, final principal destruction, terminal class and teacher deletion and complete retained audit verification after a real financial transaction. Retain only bounded outcomes. Record outstanding scenarios when the run exercises installation alone. [Browser procedure](../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-001A_Initial_Deployment_Browser_Validation.md)
4. **Close the exercise personally.** Check the workflow cleanup result and the staging project in DigitalOcean. For an interrupted run, reconcile the create activity, destroy any confirmed surviving temporary Droplet by its ID, and confirm absence. Check for separately billable volumes, snapshots, backups, reserved IPs, transfer or external services. Retire run-specific credentials and record the owner check and time. Keep the exercise open while ownership or absence is uncertain.
5. **Record what passed.** A successful maintainer installation supports the reference profile exercised. Independent verification requires another operator to repeat the handbook unaided. Python 3.14, rollback to 3.10, monitoring parity and any separate fault-injection rehearsal require their own approved scope and evidence.
