---
title: Self-hosting rehearsal findings and operator usability
category: self-hosting
description: Observed installation failures, bounded run evidence, corrected operating assumptions and proposed improvements from the first attended rehearsal.
roles: [operator]
---

# Rehearsal findings and operator usability

Recorded November 18–19, 2026 (America/Los_Angeles). This is an informative learning
record, not a new invariant or an amendment to an application contract. It
distinguishes observations from proposed changes. Update it as the rehearsal
continues; do not turn incidental maintainer practices into public requirements.

## What the rehearsal has established

The owner created one temporary DigitalOcean SFO3 Premium Intel x86-64 host
with 2 vCPUs, 4 GB RAM and 120 GB advertised disk, running Ubuntu 22.04.5.
The creation screen quoted USD 0.048/hour. Premium AMD was unavailable in
the displayed selection; this does not establish permanent regional withdrawal.
The original reference was AMD with 80 GB disk at USD 0.042/hour. The canonical
installer checks x86-64 rather than CPU vendor; the Actions allocator still
pins the AMD size. Manual allocation does not prove the Actions path works.

The owner verified firewall attachment, observed the SSH host fingerprint in
the provider console, connected using that pinned key, and confirmed the
provider ID from guest metadata. The clean checkout at
`1ed8f35704cc524a1b386057c70128fd0d21335f` was verified. A private installation
manifest and staging-only runtime configuration were prepared on the host.
The runtime parser passed. The existing staging certificate and key were
transferred through pinned SSH and reported mode 0600 with root ownership.

The first host stage failed. PostgreSQL 14.24 packages were installed and the cluster
was running; both intended Redis access groups existed, but the first CTH
service account and release directories did not. The installer passed
`cth:<installation UUID>` as the account comment. A colon is invalid in this
passwd field. The failure message suppressed the underlying command details;
the subsequent check raised an unhandled missing-account exception.

[PR #1784](https://github.com/timwonderer/classroom-token-hub/pull/1784)
changes account creation and verification to `cth-<installation UUID>`.
Its 17 targeted installer tests passed locally, and the new regression test
fails against the original marker. The owner merged the correction as
`90a635f4a8cfbd1295a877eca7bf65d30cd574d1` on November 18, 2026. The initial host journal remained
pending at `host` until the owner rebuilt the disposable guest; it was not
reset to claim success. The corrected host stage subsequently passed apply
and check on the rebuilt Ubuntu host. The owner then completed the installation
on release `90a635f4a8cfbd1295a877eca7bf65d30cd574d1`; the final stage evidence
and its limits are recorded below.

## Final rehearsal outcome — November 19, 2026

The owner completed all ten installer stages on the rebuilt Ubuntu 22.04.5
x86-64 Droplet: host, PostgreSQL, Redis, release, config, database, services,
scheduler, ingress and readiness. The installation journal remained tied to the
selected release SHA. Redis and release each produced an initial generic
external-command failure before their checks/retries passed; the cause of those
first failures was not established.

The scheduler check's journal query falsely failed because its `--grep` and
`-n 1` ordering selected no matching record. A one-invocation in-memory wrapper
added `--reverse` only to that query; canonical apply/check then passed and the
installer recorded the stage. The pinned checkout and journal implementation
were not changed on the Droplet. The permanent correction is separate work.

The owner confirmed the Cloudflare Access browser boundary: an admitted owner
session reached the staging application, and a private/unadmitted session was
challenged or denied. An unauthenticated request to the public hostname returned
an Access redirect. A direct HTTPS request to the Droplet IP timed out, as
expected with the Cloudflare-only origin firewall. This proves the tested gate
and network path, not the application principal or classroom authorization.
This boundary follows [DOM-OPS-001](../DOMAIN/DOM-OPS-001_OPERATIONS_DOMAIN.md):
Access admission does not replace normal Identity authentication or application
authorization.

The staging database was streamed over strict host-pinned SSH directly through
age encryption into a mode-0600 local archive. No plaintext dump file was
created. Archive decryption/list validation reported 615 entries. Restore into
the isolated local PostgreSQL 14.24 database succeeded; it contained 47 public
tables at migration `a0faf8b2a35d`. The local recovery server was stopped after
verification. Production databases and production backup tooling were not used.
This proves archive readability and database restore to that target; it does
not prove application startup with restored runtime keys, row-by-row equivalence,
off-device key custody or disaster recovery from loss of the workstation.

The first local start attempt used Homebrew's `libpq` 18 `pg_ctl`, which lacked
its matching PostgreSQL server binary. The version-matched PostgreSQL 14 command
then reported an existing PID file. A host-visible process check and socket
probe showed that the isolated PostgreSQL 14 server was already running; no PID
file was removed. Use matching-version `pg_ctl` and `pg_isready`, and inspect the
recorded PID before considering removal of a lock file.

The owner reports the temporary Droplet destroyed. No separate billable cloud
resources were created, so the Droplet was the only cloud resource requiring
cleanup. Destruction was not independently checked through the provider API.
The last observed firewall rule allowed SSH from `0.0.0.0/0` so the
DigitalOcean web console remained usable. The owner had found that restricting
SSH to their current IP removed web-console access. Treat this as an observed
account/provider tradeoff, not a universal DigitalOcean requirement; the
Droplet has been destroyed and no additional cleanup was identified for this
run.

During service startup, Gunicorn logged a control-server error because its
`/nonexistent` home is read-only. The web unit remained active and readiness
passed, but the error was not investigated further. The staging certificate
was installed manually; automatic renewal and reload were not tested.

This was a bounded infrastructure and recovery rehearsal, not the full first-
deployment browser validation in SOP-DEP-001A. Separate teacher/class identity
and isolation scenarios, application login and recovery workflows, real
financial transaction audit-chain verification, terminal deletion, Redis
restart/expiry behavior, certificate renewal, rollback, and an unaided second-
operator run were not performed. Do not describe them as passed.

## Corrected assumptions

| Topic | What belongs in public guidance |
| --- | --- |
| Operator organization | One teacher or infrastructure owner can operate CTH. No corporate operations team, permanent coordinator, lease database, heartbeat service or autonomous cleanup service is inherently required. |
| Cloud provider | DigitalOcean and SFO3 are the current reference, not universal application requirements. A separate project organizes staging; it does not establish team-level credential isolation. Do not claim a token cannot access production merely because resources are in another project. |
| Creation and destruction | The owner chose manual console creation and exact-resource manual destruction. Actions is an optional rehearsal tool. Never delete every resource except a known production name. Owner-confirmed absence is useful evidence and should be labeled as such rather than requiring redundant API proof. |
| Cost | Show the live quote and explain billing until destruction. No strict two-hour autonomous deletion guarantee was requested. Teachers should not have to keep an idle host while maintainers review a bug fix. Offer an explicit stop, preservation and cleanup path; do not destroy resources without authorization. |
| Network | Review actual configured destinations and protect ingress. Unrestricted outbound access is supported by the corrected reference. Do not impose a blanket egress allowlist without a supported need. A public documentation or marketing link is not production business-state access. |
| Hostname and gate | A gated subdomain of an existing domain is sufficient for this rehearsal. No new purchased domain or Cloudflare Tunnel is necessary. A configured Access policy can be reviewed before a guest exists; admitted application access and direct-origin denial need the installed host. |
| Access hostname | The public application hostname and the Access login hostname are different manifest fields. Show a concrete example of each and explain how to obtain the login hostname. A login-page screenshot establishes the destination, not successful application authorization. |
| TLS | Use the existing valid staging Let's Encrypt certificate. Cloudflare Origin CA and client certificates are not required by this reference. Manual DNS issuance does not establish automatic renewal; long-lived operation still needs a tested renewal and reload path. |
| Monitoring | A suitable generic monitor may be sufficient. The hosted status stack and a specialized monitoring certificate are not core installation prerequisites. An Access login response is not application-health evidence. |
| Credentials | Generate application keys on the target and enter provider credentials privately, as production does. Do not require GitHub application secrets for a manual install. Use independent staging credentials; never copy production keys or records. |
| Environment mode | `FLASK_ENV=production` selects the reference security behavior even on staging. Host, data and integration isolation determine which deployment is affected. The installer does not accept a `staging` value. |
| Recovery workstation | Inspect existing tools before requiring installations. The owner's Mac already had usable age, Python and PostgreSQL 14 tools. A separate Unix-socket-only local cluster supplied empty staging restore targets without changing existing databases or production backup tooling. Other operators may use another suitable isolated recovery target. |
| Backup keys and restore | The staging age key encrypted a real staging custom-format dump, which decrypted/listed and restored into the isolated local target. Keep the private identity off the server. Separate local folders are not off-device key custody, and the rehearsal did not prove restored application operation with runtime keys. |
| Console and SSH access | The web console initially stalled and later connected; the cause was not established. The owner reported that an SSH source-IP restriction prevented web-console access, so SSH remained open to all IPv4 sources during the exercise. This was a deliberate access tradeoff for this run, not a general provider rule. The Droplet was destroyed; no firewall cleanup remains for this run. |
| SSH passphrases | A protected SSH key may require an operator's private interactive prompt. A failed batch login does not prove the key is wrong. Preserve host-key verification without asking for the passphrase in chat. |
| Instructions | Label commands “on your Mac” or “on the server,” show the expected prompt and success output, and keep secret material out of screenshots. Short operator steps are preferable to repeated unexplained terminal blocks. |

## Maintainer responsibilities versus operator requirements

Maintainers own fixing installer defects, reviewing PRs, publishing releases,
running CI, proving clean-host installation, and documenting supported recovery.
An operator should be able to choose a published supported release and retain
a receipt identifying it without participating in that development process.
The current exact-SHA interface is an implementation constraint, not a reason
to require every teacher to perform a source review or create a branch.

The first release should establish one usable, tested path. Provider choice
does not mean every possible topology is already supported. Keep genuine
requirements explicit: lawful use, protected credentials, correct schema,
secure access, authorized business workflows, audit integrity and recovery.
Do not relax application identity, tenant isolation, FEAT mutation ownership or
deletion contracts to compensate for infrastructure usability problems.

## Proposed improvements, not implemented guarantees

1. **Pre-spend checks.** Validate as many local inputs and package prerequisites
   as possible before allocation. Report separately what requires a live host.
2. **Simple release selection.** Resolve a supported release to immutable source
   automatically and retain that identity in the receipt. Avoid requiring the
   teacher to manage GitHub review or SHA bookkeeping manually.
3. **Actionable failures.** Identify the failing operation and provide bounded,
   sanitized diagnostics. Missing expected accounts should produce a clear
   incomplete-stage result rather than a traceback. Never dump runtime secrets.
4. **Safe resumption.** Verify completed work and ownership before continuing.
   Preserve keys and data, refuse foreign resources, and avoid duplicate writes.
   The current journal only acknowledges interrupted stages whose complete
   postconditions already pass; it does not resume arbitrary partial work.
5. **Supported installer repair.** Design an explicit transition that preserves
   old/new installer provenance, host ownership, completed work and application
   release compatibility. Do not implement it by silently changing the pinned
   SHA, overwriting enrollment, or editing the stage journal. Separate installer
   and application release identities only with an explicit compatibility design.
6. **Affordable stop and retry.** Explain what can be preserved privately, what
   cleanup costs remain, and what can be reused. Distinguish a maintainer's
   clean-host validation run from an operator's supported repair procedure.
7. **Teacher usability validation.** Have another operator follow the published
   instructions without undocumented assistance. Record confusing steps and
   required interventions; a successful maintainer run alone is insufficient.

These improvements need scoped implementation and validation. The present
record neither authorizes infrastructure changes nor claims repair support
that the shipped installer lacks.

## Rebuild rather than replace the resource

The owner identified DigitalOcean's Rebuild option after destruction and
recreation had been proposed. A reboot preserves installed state; a rebuild
from a clean Ubuntu image wipes the disk and can supply a fresh installation
target while retaining the public IP. A new cloud resource is not inherently
required for clean-host validation. Prefer evaluating the provider's existing
reset mechanism before asking an operator to repeat resource enrollment.
[DigitalOcean rebuild documentation](https://docs.digitalocean.com/products/droplets/how-to/rebuild/)

Rebuild is destructive, not an in-place installer repair. The failed guest's
manifest, runtime secrets, packages and journal are lost. Keep needed inputs
privately outside the guest, choose the same approved OS baseline, and verify
the new SSH host key and machine identity before supplying secrets. Do not
silently accept a changed SSH fingerprint. The owner subsequently completed
the rebuild. The new console-observed host key matched the network key; guest
metadata retained the provider ID and all four old installation paths were
absent. A subsequent SSH-terminal screenshot showed the corrected release
and manifest prepared, then successful `apply host` and `check host` receipts.
The later owner-attended run completed all installer stages, exercised the
Cloudflare Access boundary, and restored an encrypted staging database backup
locally as recorded above. The owner reports the Droplet destroyed; no other
billable cloud resources were created. These results do not establish full
application acceptance or independent handbook reproducibility.
