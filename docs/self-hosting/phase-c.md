---
title: Phase C staging execution plan
category: self-hosting
description: Approval, budget, ownership checks and acceptance gates for the first temporary cloud installation.
roles: [operator]
---

# Phase C execution plan and resource ownership review

**Proposed for owner approval.** The B3 tests exercise provider responses and host operations through isolated fixtures. A real dispatch requires separate authorization for the application release, controller revision, spending limit, credentials, destinations and cleanup owner. This plan covers the first Python 3.10 reference run. Prepare the [guest enrollment inputs](staging-bootstrap.md) before allocating the host.

## Proposed authorization

| Decision | Value to approve or record privately before allocation |
| --- | --- |
| Compute | One DigitalOcean Basic Premium AMD Droplet in SFO3, size `s-2vcpu-4gb-amd`, 2 vCPUs, 4 GB RAM, 80 GB advertised disk. Record and verify the exact public Ubuntu 22.04 x86-64 image ID. No volume, reserved IP, backup or snapshot is required. |
| Runtime | Proposed first application SHA `4427fd683475d56b0e5937e5cda93badff40c444`, the reviewed B2 reference release. Enroll the controller and workflow SHAs separately, and confirm the workflow is available on the protected default branch. Use Python 3.10, PostgreSQL 14.24 and two isolated Redis instances. Verify that the approved Jammy package source actually offers 14.24 before dispatch. |
| Time and spend | Proposed working window 60–90 minutes, maximum lease 120 minutes from reservation. Approve at most USD 0.05/hour and USD 0.10 for Droplet compute. The selected USD 0.042/hour rate gives about USD 0.084 at two hours. Verify the current size quote at dispatch. The ceiling controls admission and teardown eligibility. Billing can exceed it if deletion cannot be confirmed. |
| Cloud identity | Use a dedicated staging-only team and default project, approved VPC and reviewed firewall. Record their immutable IDs and the identity authorized for each operation. Project tagging alone cannot limit a team-scoped token. Use credentials with no access to production. |
| Networking | Enroll the coordinator's management path and the staging-only gated HTTPS origin. Confirm approved SSH access, restricted inbound policy and outbound enforcement for package sources, provider services and the private staging destinations. Inspect the actual rules and routes, including VPC peering and IPv6. A hostname allowlist alone cannot enforce egress. |
| Credentials | Reserve a distinct SSH identity and enrollment for this run. Supply the runtime file and TLS material privately, with new session, lookup, encryption, export and audit keys. Supply staging registrations for Turnstile, Passwordless and restricted ingress. Keep cloud and GitHub control credentials off the guest. Inventory external registrations and designate who retires or rotates them. |
| Operations | Name the operator, the person who can reconcile a disputed resource in the provider console, and the alert destination. One operator can hold both roles. Confirm independent timer operation and that the inventory will survive runner loss. Record who can recover it if the coordinator itself fails. |

Stop bootstrap and tests by minute 115 to leave five minutes for cleanup. The independent timer checks every minute. Assign an operator to act if the provider still reports a resource at minute 120. Keep the one-run lock in force until ownership, absence and external credential retirement are reconciled. An approval for one dispatch does not cover a second fault-injection run.

DigitalOcean bills bundled CPU Droplets until destruction, including time spent powered off. At the first rehearsal, reconcile billing and check retained backups, volumes, snapshots, reserved addresses, egress and any separately enrolled DNS, tunnel or authentication services. Account for their charges separately. [Droplet billing](https://docs.digitalocean.com/products/droplets/details/pricing/)

## Coordinator readiness

Use the control-host enrollment procedure in `infra/staging/README.md` from the exact controller checkout. The coordinator must already have a private route to the staging VPC. Its protected inventory and service account persist between runs. A fresh staging team still needs an enrolled default project, firewall, VPC and access policy. Validate the current API response shape and scopes during the separately authorized cloud rehearsal. [Droplet API](https://docs.digitalocean.com/reference/api/reference/droplets/) · [Project resource membership](https://docs.digitalocean.com/reference/api/reference/project-resources/)

The cloud operator owns provider-ID reconciliation. The credential owner attests to retirement of the external enrollments after deletion. The independent timer retries outstanding work. The GitHub artifact describes the outcome at collection time. Use the coordinator's private inventory to resolve later cleanup, then record the final outcome. Set the sanitized artifact retention to three days. Retain the ownership record while any costs, resources or credentials remain disputed.

## Run and acceptance gates

1. **Authorize.** The owner signs off the exact run, release, profile, expiry and budget. Protect the workflow environment and coordinator installation. Verify no other lease is active and no unresolved allocation remains. Rehearse the operator recovery path before approval.
2. **Allocate and identify.** Reserve ownership durably before the provider create request. Verify actual provider identity, project, VPC, image, size and firewall. The Phase C operator must witness the new host's SSH public key through the authenticated provider console and bind it to this run and numeric Droplet ID. Check console access under the restricted firewall in advance. Verify guest metadata over pinned SSH. Stop and reconcile disagreement before delivering any application credentials.
3. **Install.** Transfer the reviewed release and staging-only inputs. Run the canonical stages in order. Check PostgreSQL, the expected migration head and seeds, isolation of the Redis sockets, web service, a single scheduler owner, and the restricted TLS origin. Record observed stage results. Keep public admission closed.
4. **Exercise authorized workflows.** With separately approved test identities, verify an admitted and denied browser session, teacher signup, student claim and financially meaningful authorized activity. For the full acceptance exercise, use two teachers and independently owned economies with one shared student principal. Verify independent seat state, denied cross-class access, deletion of one association, destruction after the final association, and complete retained lineage. Keep domain records and raw audit material on the guest. A stage success or a skipped acceptance hook supplies no browser or financial evidence. Follow the [initial deployment browser procedure](../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-001A_Initial_Deployment_Browser_Validation.md).
5. **Retire and verify.** Finish acceptance within the deadline. On success, failure or cancellation, confirm deletion by exact provider ID. Inspect the staging inventory and ancillary resources, retire per-run credentials and resolve external integrations. In a separately approved fault rehearsal interrupt the runner after a known allocation, then observe the independent expiration job and provider-side absence. Preserve only bounded outcomes. The first controlled run does not establish independent handbook verification.

## Security and resource ownership review

| Boundary | Required behavior | Remaining real-world evidence |
| --- | --- | --- |
| Dispatch to cloud authority | Manual dispatch, explicit out-of-band approval and a fixed trusted controller constrain the permitted release and hardware. A GitHub runner does not need the provider token. | Check environment reviewers, workflow/ref protection, coordinator key restrictions and staging team credential scopes. |
| Ambiguous create | Persist intent before creating. A timeout can mean that the VM exists. Keep the lease and investigate; never submit a replacement while the first allocation is uncertain. | Compare a real provider creation record, observed guest identity, project membership and inventory. |
| Destructive authority | A matching name, tag, IP, age or empty list cannot by itself authorize deletion. Require ownership evidence for the exact ID and confirm absence using the enrolled provider identity. Conflicts block further allocation. | Witness retention of an unresolved resource, operator notification and billing reconciliation. |
| Guest and CI access | Limit transfer to the authorized guest. Rate-limit and student state, external credentials, cookies, audit events and full process output are outside CI evidence. Reject unexpected output instead of archiving it for diagnosis. | Inspect actual redacted artifacts, provider-specific logs, TLS and admission. Test the negative access boundary without probing production. |
| Independent expiration | A coordinator timer and durable inventory survive runner loss. Provider outages, host outages, revoked tokens or lost inventory require operator intervention. | Verify timer alert delivery, restoration of the inventory, staged credential revocation and absence of residual charges. |

Three review findings directly affect Phase C sign-off:

1. **High impact, covered by a regression.** A newly accepted Droplet can be temporarily absent from both the ID lookup and project listing. Closing a lease on that observation could leave a subsequently visible, billable VM unattended. The lifecycle requires a positive ownership check and durable deletion intent before accepting later absence. Ambiguous creation without a receipt needs independent guest proof. Inspect `infra/staging/lifecycle.py` (`identify`, `cleanup`) and its delayed-visibility and duplicate-candidate tests.
2. **High impact, requires operator evidence.** A mock cannot prove that the staging token lacks production reach, the actual firewall enforces the reviewed rules, or the operator can witness the intended guest key. The provider adapter checks the enrolled team/project, firewall, image and quote. Bootstrap checks the protected pin, guest metadata and installation UUID before private transfer. Witness these boundaries in the provider console. See `infra/staging/digitalocean.py` (`preflight`) and `infra/staging/bootstrap.py` (`_identity`).
3. **Operational impact, independently tracked.** Provider absence can precede revocation of a tunnel or acceptance credential. The coordinator keeps a retirement obligation outside the worker and holds further runs pending a matching receipt. Monitor the timer, preserve its inventory and check its current disposition if the runner artifact predates retirement. See `infra/staging/controller.py` (`retire`, `sweep`).

Releasing the admission gate for general users, production access and a Python 3.14 migration are outside this execution plan.

## B3 offline verification record

From the controller checkout, a developer can run `python3.10 -B -m unittest discover -s infra/staging` without staging credentials. All 30 tests passed: 16 provider/lifecycle tests, seven coordinator/workflow tests and seven guest-bootstrap tests. The final verification also blocked Python network connections and DNS lookups. Tests used temporary SQLite inventories, local Git bundles and keys, and fixtures for provider and guest responses. They exercised the workflow's actual artifact filter with malformed, oversized and sensitive output. The two handbook navigation/command tests and static workflow validation with `actionlint` passed.

These checks did not dispatch GitHub Actions, contact DigitalOcean, install or start the systemd timer, enroll an external provider or attest to cloud deletion. Use the Phase C gates above for those observations.
