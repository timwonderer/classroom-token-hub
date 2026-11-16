---
title: Contract for an ephemeral staging run
category: self-hosting
description: Inputs, admission checks, evidence and independent cleanup for a future staging controller.
roles: [operator]
---

# Contract for an ephemeral staging run

**Proposed B3 interface.** B2 supplies the host installer. A future manually dispatched controller will arrange infrastructure, call the published stage commands and run a separate synthetic acceptance workflow. No staging resources are required to read or locally test the handbook.

## Before dispatch

| Input | Required decision or validation |
| --- | --- |
| Release | Full reviewed application Git SHA containing the installer and baseline. Pin the controller/action revisions independently. Record Python 3.10, PostgreSQL 14.24 and the selected Ubuntu 22.04 x86-64 image identifier. |
| Capacity | One SFO3 Basic Premium AMD Droplet, 2 vCPU, 4 GB, 80 GB advertised disk. Approve the plan, run budget, latest permissible destruction time and artifact expiry. Refuse to start with missing limits or another active run. |
| Ownership | Separate staging project and a dedicated API identity limited to required resource operations. Label every object with a unique run ID and expiry. Persist exact provider IDs, owner and project in a restricted inventory outside the runner. |
| Networking and providers | Dedicated private network, hostname, validated origin certificate, separate admission policy, operator-approved ingress, synthetic email/notification destinations and staging-only authentication credentials. Restrict routing and egress to the approved installation and validation destinations. Status parity remains disabled until collector targets and Firestore project selection can be isolated. |
| Configuration and secrets | New installation UUID, observed machine ID, explicit database and the full installation manifest. Inject staging-only session, encryption, audit and lookup material and provider credentials through the protected runtime file. Keep cloud-control credentials outside the Droplet. Independent PostgreSQL and both Redis databases start empty. |

## Run and evidence

1. Acquire the one-run concurrency lock, reserve the approved cost/lifetime budget, and persist the ownership record. Before creating the resource, provision the expiry record for cleanup outside GitHub Actions. Resolve a timed-out create response using the exact run identity before attempting another create.
2. Provision the temporary host from the selected image. Authenticate its identity, compare the actual size and region to the approved configuration, and transfer the reviewed checkout, manifest and secret inputs privately. Invoke the same operator interface, in the same stage order, as the [reference installation](reference-installation.md). The controller runs no alternate install or database seed path.
3. Require successful stage results for the same installation UUID and release SHA. Complete real restricted-access, browser, service restart, scheduler and integration checks. Run lawful synthetic teacher signup, classroom creation, seat claim and scoped business operations. Exercise deletion and surviving relationships. Verify nonempty expected audit evidence and the complete chain head. The test report must distinguish classroom fixtures, external browser outcomes and host-local readiness observations.
4. Return a sanitized result per stage and acceptance scenario with action, release, installation ID, versions, timestamps and outcome. Attach the failure class and bounded signal where needed. Raw environment files, URLs containing credentials, cookies, authentication factors, classroom records, audit keys, databases and full service logs must stay out of artifacts. Apply the approved expiry to artifacts.
5. Set the teardown outcome independently of test success. Verify the exact resource ID, owning project, run ID, tag and eligibility in the persisted inventory. Quiesce the test and destroy only matching resources. Check absence by provider ID and inspect attached storage, snapshots, IPs, DNS, edge policies, temporary principal grants, notifications and artifact retention. Revoke staging-only secrets according to the run policy. Conflicting ownership or absent evidence triggers manual reconciliation instead of blind deletion.
6. An independent expiration job reconciles abandoned runs after controller, cancellation, network or runner failure. Persist incomplete cleanup, retry within the approved scope and notify the operator on overdue inventory, billing exceptions or unresolved ownership. Powering off a Droplet leaves compute billing active. Detached volumes, snapshots, reserved resources and third-party services have independent lifecycles.

A separate authorized run can evaluate Python 3.14 only after a successful 3.10 reference installation. Hold OS, database, commit and acceptance workload constant; test both the interpreter upgrade on populated synthetic state and the switch back to the known working runtime. Keep that evidence distinct from fresh installation.

## Reproducibility sign-off

A maintainer run establishes reference-host evidence for its exact profile after stage, browser and teardown results have been recorded. A second operator must then install from a newly provisioned host using only published steps, record any undocumented intervention, and complete functional acceptance and teardown. An accepted independent result identifies the documented release, the operator and redacted evidence.
