---
title: First use and ongoing operation
category: self-hosting
description: Verify a new deployment, protect its recovery points and retire it safely.
roles: [operator]
---

# First use and ongoing operation

This is the advanced operator reference. For the teacher walkthrough, start
with [Part 6](part-6-first-use.md) and [Part 7](part-7-keep-it-running.md).
The [rehearsal record](rehearsal-findings.md) gives the bounded host results;
the complete lifecycle procedure below has not been independently rehearsed.
Use fictional classes for validation and restrict access during operational
work. Read the [current support limits](before-you-begin.md#which-release-this-guide-matches)
before committing real classroom data.

## First operator account

Only the infrastructure operator can initiate bootstrap. Use a private interactive terminal with no recording or shared scrollback; the command displays a one-time TOTP enrollment URI, QR code and secret. In the following command, the operator sets the shell variable `sha` to the recorded full installed application SHA and confirms the release and runtime file refer to this host. The example uses the manifest’s default example path `/etc/cth/runtime.env`; substitute the enrolled `runtime_env` if it differs. Invoke the CLI through systemd with the same environment and non-root Unix identity as the app. The login is entered at its prompt.

```sh
sudo systemd-run --pty --wait --collect \
  -p User=cthapp -p Group=cthapp \
  -p WorkingDirectory="/opt/cth/releases/$sha" \
  -p EnvironmentFile=/etc/cth/runtime.env \
  "/opt/cth/venvs/$sha/bin/flask" --app app create-sysadmin
```

Enroll the authenticator and secure the recovery material privately. Verify access to `/sysadmin/login` with the new credentials. A successful bootstrap creates one system principal. A duplicate login preserves the existing principal. If enrollment fails or output is lost, use the authorized recovery procedure. Repeating the command cannot reveal the original secret. The console has no seat, class or account-creation route. [Operator bootstrap contract](../FEATURE-EXECUTION/FEAT-IDEN-008_OPERATOR_SYSADMIN_BOOTSTRAP.md)

## First classroom and transaction

Use fictional names on an isolated rehearsal. Use the site's normal browsers, forms, sessions, CSRF protection, deployed Turnstile and real authentication providers. Separate role sessions using distinct browser profiles.

| Authority and action | Verify | If it fails |
| --- | --- | --- |
| **Teacher:** sign up at `/admin/signup`. Enter classroom and section information, a username, then confirm TOTP. Sign in at `/admin/login`. | The teacher sees their own classroom. Its display name and join code cannot authorize access to another teacher's classroom. | Inspect admission, time synchronization and provider configuration. Repeat through the signup workflow. Never provision the user by SQL. |
| **Teacher:** in the selected classroom, add the intended student seat through roster setup. **Student:** visit `/student/claim-account`, enter the classroom join code and the name supplied by the teacher. Complete the challenge, disambiguation if prompted, and the PIN/passphrase setup flow. Sign in at `/student/login`. | The student has a claimed seat in the intended class. Ephemeral setup data uses the private setup Redis service. | Recheck roster spelling, selected classroom and private setup-store health. Inspect service status without recording claim inputs. [Seat provisioning](../FEATURE-EXECUTION/FEAT-IDEN-006_PROVISION_STUDENT_SEAT.md) · [Student claim](../FEATURE-EXECUTION/FEAT-IDEN-001_UNAUTHENTICATED_STUDENT_SEAT_CLAIM_REMEDIATED.md) |
| **Teacher:** configure the selected class's economy through its dashboard. In an isolated classroom, submit one manual payroll credit for a fictional seat from the manual-payment form on `/admin/payroll`. **Student:** sign in and view the selected seat's ledger. | The authorized credit appears once for the intended amount, class and seat. Verify the teacher payroll history agrees. | After a timeout, inspect history before resubmitting. A correction must use the permitted reversal workflow. [Payroll execution](../FEATURE-EXECUTION/FEAT-PROD-003_RECORD_PAYROLL_EVENT.md) |
| **Verifier:** verify creation evidence for the expected protected row and the entire class chain to its expected head, including sequence, count and digest. | The verifier authenticates the protected amount and creation event. B1's repeatable rollback-only example has exact target prerequisites and a command in the [database chapter](fresh-database.md). | Empty, unavailable, truncated or mismatched evidence keeps the release gate closed. Preserve the bounded diagnostic result for investigation. [Audit lineage](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md) |
| **Independent test teachers and student:** on the rehearsal host, create two separately owned classrooms. Enroll separate seats for one fictional student using the supported add-class and switch-class flows. Attempt cross-class access with each teacher session. In the normal classroom and account deletion flows, remove one association, then the final one. | One student's identity can serve both seats. Economic state and teacher authority remain local. After the first deletion the legitimate surviving association works. After the final seat disappears the unassociated student principal is destroyed. Teacher-account destruction removes its owned classroom state. Retained audit evidence remains verifiable. | Stop if authority crosses a tenant boundary, deleted state is accessible or lineage is incomplete. Preserve redacted evidence. Never use production classes for adversarial or deletion tests. [Initial browser validation](../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-001A_Initial_Deployment_Browser_Validation.md) · [Teacher account destruction](../FEATURE-EXECUTION/FEAT-IDEN-007_TEACHER_ACCOUNT_DESTRUCTION.md) |

The verifier also exercises Passwordless enrollment and sign-in, Turnstile on its configured routes, role-specific sessions, accessibility, and newly restarted services from outside the host. Observe both authorized access and denial to an unadmitted visitor; test that direct access cannot bypass the external gate. Record the commit, date, platform, outcome, verifier and bounded failure reason. Exclude cookies, TOTP, request bodies, names, class and seat inventories, full logs and database dumps. Release balance verification in the production-transition SOP is a read-only external operator activity. Application-scoped verification is governed by [DOM-OPS-001](../DOMAIN/DOM-OPS-001_OPERATIONS_DOMAIN.md).

## Monitoring and troubleshooting

Host root can rerun `python3 infra/self-hosting/install.py check readiness --config "$manifest"` with the verified installation manifest. An exit-zero result describes the probes the stage actually implements. Check bounded database health, service restart behavior, the single scheduler owner and scheduled execution during the intended interval. An unknown status signal remains unknown until its probe runs. Verify the host clock and time zone before interpreting payroll or rent timing. Optional status publication, notification delivery and log ingestion require their own end-to-end checks with authorized test destinations. The [integration inventory](handbook-overview.md) identifies hosted defaults.

| Symptom | Authority and diagnostic action | Recovery |
| --- | --- | --- |
| Gunicorn fails or restarts | Root inspects `systemctl status --no-pager cth-web.service` privately, then checks the configured release and runtime preflight. | Correct the missing prerequisite and restart through the approved service procedure. Keep raw log output private. |
| Student claim/setup fails while health is green | Root checks the `redis` and `config` stages and service socket ownership; teacher verifies the unclaimed seat in their own active class. | Fix the dedicated setup instance or client configuration. Keep memory-only safeguards enabled. |
| Duplicate or absent scheduled execution | Root checks the `scheduler` stage, service processes, the configured owner and bounded execution evidence across a restart. | Keep access gated until exactly one owner runs. Reconcile any financial effect through the owning business workflow. |
| Actual browser receives the wrong certificate, a public page or redirect loop | Ingress owner checks public DNS, certificate hostname, Cloudflare proxy routing and admission identity policy. | Restore restricted access and repeat external allow/deny checks. A local health response alone is insufficient. |
| Database mismatch or unversioned schema | Root compares the enrolled target and B1 evidence with the [partial-install procedure](fresh-database.md). | Keep it offline. Safely dispose of a confirmed new disposable database or use approved recovery for an established installation. |

## Backups, restoration and deletion

Before admitting classrooms, establish encrypted, access-controlled recovery points on separate storage and complete a restore drill. Define recovery point and recovery time objectives, key custody, retention and a deletion procedure. Include the database, release identity and the protected key material required for decryption and audit verification under separate access controls. Exclude the student-setup Redis, temporary credentials, raw identity data in logs, and secrets in public evidence. A write-capable application login is unnecessary for the backup reader. [Credential and backup operations](../STANDARD_OPERATING_PROCEDURES/SECURITY/SOP-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_OPERATIONS.md) · [PII storage and retention](../INVARIANT/ARCHITECTURE/INV-ARC-018_PII_STORAGE_AND_RETENTION_ENFORCEMENT.md)

The repository's `infra/db-backup/cth_db_backup.py` is used by the production
pre-release procedure. The [v2.4.5 deployment record](https://github.com/timwonderer/classroom-token-hub/blob/main/docs/ops/audits/DEPLOY_2026-11-14_1d74ea8.md)
records a successful encrypted backup, comparison of all 47 table counts,
restore matching the manifest and revision, and a successful deleted-identity
check. Reuse that evidence for the same tool and prerequisites; a different
host does not by itself invalidate it. This does not establish that the proposed
nightly timers or remote-storage deployment were installed.

The tool requires private configuration for the source reader, a dedicated
disposable verification database, the age public recipient and private state
directory; remote storage is optional. Its verification routine resets its
designated scratch database. Confirm that endpoint belongs exclusively to this
backup deployment. The production `prerelease.sh` wrapper hardcodes `root@cth`,
the `classroom-economy` service and the owner's Mac paths: do not run it unchanged
against a self-hosted installation. Review `infra/db-backup/README.md` and use
the configurable tool below with your own endpoints. The host installer does
not provision these backup roles or a verification database.

| Authority and command after provisioning the backup utility | Expected result | Failure and recovery |
| --- | --- | --- |
| **Backup operator**, from the checkout with the backup service's restricted configuration: `python3 infra/db-backup/cth_db_backup.py backup --reason manual` | An encrypted artifact, matching manifest and scratch restore with correct revision and table counts. Check off-host acknowledgement and checksum independently. | A missing manifest, stale point or failed verification is ineligible for cutover. Repair credentials/storage and create a verified point. |
| **Recovery operator**, on a private recovery host with the age identity. Set `artifact`, `backup_manifest`, `identity_file`, `empty_target` and `current_reader` explicitly; use credential-free PostgreSQL URLs with separate protected credentials. Run `python3 infra/db-backup/cth_db_backup.py restore --artifact "$artifact" --manifest "$backup_manifest" --identity "$identity_file" --target-url "$empty_target" --live-url "$current_reader"`. | An originally empty isolated target matches the manifest and Alembic revision. Compare surviving subjects to the live source. Exercise audit verification and application read checks privately before approving any switch. | Reject a populated target, obsolete point, missing key or deleted identity. Isolate the drill target and resolve the discrepancy. If the current source is lost, evidence of no resurrection is required before serving restored data. |
| **Data owner**, after protected destruction | Retire recovery points that could reintroduce the destroyed seat, class, or account. Verify the replacement point and reconcile every local, remote, snapshot and retained copy against the permitted lifecycle. | Restrict access to affected backups; an older point cannot be used to recreate a deleted identity. Escalate an unverifiable destruction or a provider retention conflict before reopening. |

An immutable audit event may retain lawful historical identifiers after classroom business records disappear. Do not rewrite it, fabricate a replacement, or make a deleted classroom visible to satisfy a check. [Hard deletion](../INVARIANT/ARCHITECTURE/INV-ARC-012_HARD_DELETION_ENFORCEMENT.md) · [Audit lineage](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md)

## Upgrades and runtime rollback

1. **Release operator.** Keep the audience gate restricted. Record current SHA, exact Python environment, services, database revision and verified recovery point. Stage the reviewed successor release with its own Python environment. Read release notes, migration ancestry and the release's `migrations/forward_only_register.txt`. A rebuild of an existing database through the fresh installer is outside the upgrade procedure.
2. **Migration operator.** In a private, release-pinned environment using the explicitly identified migration owner, run `flask db current` and `flask db heads`; expect the documented current revision and exactly one release head. Rehearse `flask db upgrade` against an isolated authorized upgrade target and confirm the expected head and acceptance checks. For the actual upgrade follow the [production transition procedure](../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-002_Production_Transition_Runbook.md), including backup, restricted writes, versioned migration, service activation and external verification. For every newly introduced object, apply its reviewed runtime privileges as the schema owner and test a real service-account read or permitted write in rehearsal. This profile grants permissions on reviewed objects and has no blanket grant on future tables. Stop on unexpected revisions, missing privileges or unsuccessful health checks.
3. **Release operator.** If the new runtime fails with a schema compatible with the prior release, restore the previous verified application, Python environment, configuration and service binding. Check the head, restricted login, financial verification and scheduler ownership again. If data or schema changed incompatibly, select a reviewed forward fix or eligible restore under the deletion controls above. A downgrade requires a previously rehearsed explicit revision and compatible migration path.
4. **Verifier.** Record commit, versions, evidence and the decision before changing admission policy. A later Python 3.14 trial must preserve the known working 3.10 environment and exercise return to it while holding Ubuntu and PostgreSQL constant. Setting `"python": "3.14"` in the installation manifest installs CPython 3.14.10 from the pinned python-build-standalone `20261110` release under `/opt/cth/python/3.14` after a SHA-256 check, and builds the release environment from it. Ubuntu's `python3.10` stays installed for the return path. Ubuntu does not update this interpreter; a security fix means reviewing and pinning a newer build.

## Decommissioning

1. The infrastructure owner confirms the target host, installation ID, provider resource IDs, release, retention obligations, approved disposition of audit evidence and backup copies. If ownership or retention is uncertain, suspend admission and postpone destructive actions.
2. The operator restricts access. Authorized classroom owners complete the terminal class and identity workflows while services are still available. Verify final-seat deletion, surviving unrelated associations, protected destruction and retained cryptographic evidence as applicable. Collect only an approved redacted closeout record.
3. Root quiesces the scheduler and web service and checks that no writer remains. Stop the ingress, both Redis services and application connections. Review the database disposition and all copies with the data owner. Disable scheduled backups so they cannot repopulate storage. Retire provider credentials, DNS, notifications and identity registrations for this deployment.
4. The infrastructure owner reconciles retention before releasing storage or destroying key material. Remove separately held snapshots, volumes, artifacts or backups when their authorized retention expires. Where destruction is authorized, match exact resource IDs to the signed inventory, destroy them through the provider and verify their absence. Record retained resources, expiry and responsible owner. A failed cleanup stays open until verified.
