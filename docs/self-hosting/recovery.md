---
title: "Recover onto a replacement server"
category: self-hosting
description: Restore matching CTH data and keys, verify the replacement, and move the web address without running two schedulers.
roles: [operator]
---

# Recover onto a replacement server

A database restore puts records back into storage. **Server recovery** gets
CTH running with those records, their original encryption keys and the right
permissions, then moves your web address to the replacement.

You can learn these steps and work through them with an AI agent. The useful
question at each checkpoint is: **What do we now know about this copy?** An
archive that decrypts, a database that restores and a classroom that works are
three different checks.

**Agent prompt to work through the whole recovery:**

```text
Guide me through docs/self-hosting/recovery.md one checkpoint at a time.
Read the installer and runtime source at my recorded release before adapting
commands. Begin with a read-only inventory of old/new hosts, backup filenames,
release identity and deletion-eligibility evidence. Tell me which terminal
to use, what will change and what output means success. Keep the old app
disabled at boot and inactive, including after a reboot. Identify automation
that could restart it. Preserve original application keys and the new host's own manifest,
and never reset the installer journal. Keep secrets and identity sets out
of chat. Distinguish static checks from a tested restore and browser recovery.
Pause on a failed check and identify the cause before attempting a repair.
```

> [!NOTE]
> **Practice this with fictional classes first.** The database tools have been
> exercised in other procedures. This complete replacement-server walkthrough
> has not yet been rehearsed on the self-hosting layout. The manual continuation
> below follows the source in this handbook's snapshot; it is not a new
> recovery command built into the installer. Record the actual results of your
> practice run, including failures.

## 1. Decide which situation you are recovering from

| Situation | Start with |
| --- | --- |
| The site stopped working, but the server and database still exist. | [Troubleshooting](troubleshooting.md). A restart or configuration repair may be enough. Preserve the existing data while investigating. |
| You are moving to another server and the old one works. | Disable and stop the old app as in step 2, take and verify fresh database and key backups, then follow this page. |
| The old server is lost, but you have both backups and the backup private key. | Follow this page using the last eligible recovery point. Record which work happened after that point and may be lost. |
| You have a database archive but no matching application keys. | Find the protected settings backup or a surviving copy of the original runtime file. New keys cannot decrypt the old records. |
| You suspect the server or its keys were compromised. | Preserve what remains and separate recovery from incident investigation. Have your agent identify exposed keys and the relevant rotation procedures before reusing them. This page assumes loss or failure, not a proven compromise. |

A recovery point is **eligible** when it is complete, readable, and allowed to
be restored. A recent date alone isn't enough: restoring an old class or
account that was deliberately deleted would bring back data that should be
gone. The [retention rules](../INVARIANT/ARCHITECTURE/INV-ARC-018_PII_STORAGE_AND_RETENTION_ENFORCEMENT.md#vii-prohibited-storage-patterns)
apply to restored copies too.

**Record in your private installation note:** old server IP, replacement server
IP, CTH hostname, backup filenames, backup time, matching release SHA and the
last successful restore test. Label old and new clearly. Keep student names,
identifiers and keys out of a public recovery report.

## 2. Freeze the old copy and choose the recovery point

**Work here: the old server terminal, if it is reachable.** Close general web
access with [Cloudflare Access](part-7-keep-it-running.md#710-optional-maintenance-mode-with-cloudflare-access),
then disable and stop the app and its HTTPS front end:

```bash
systemctl disable --now cth-ingress.service cth-web.service
```

`--now` stops both services immediately. `disable` removes their normal
start-at-boot links, so an ordinary reboot does not bring the old app back
while the replacement is running. Check both settings separately:

```bash
systemctl is-enabled cth-ingress.service cth-web.service
```

Expect `disabled` twice. Then:

```bash
systemctl is-active cth-ingress.service cth-web.service
```

Expect `inactive` twice. These checks return a nonzero exit status for
`disabled` and `inactive`; those are the intended results here, not failures
to clear by enabling or starting the services. The database remains running,
so you can take the two backups in [Part 7](part-7-keep-it-running.md#72-back-up-the-database)
from your computer. In this same stopped window,
[save the independent audit baseline](upgrades.md#save-the-expected-baseline-with-a-recovery-point)
and pair it with the database and key backups. Test the database backup with
Part 7.4 before continuing. If the old source is lost, use the trusted baseline
already saved with the chosen recovery point; don't generate it from the
restored copy.

**Why disable both?** Cloudflare Access controls who can enter the website.
It doesn't stop payroll, rent or other timed jobs. Stopping `cth-web` stops
that copy's scheduler. The installer enables both services for boot, and the
HTTPS service can start the app through its dependency, so merely stopping
them once is insufficient. You must not let the old and replacement copies
run their classroom jobs independently.

> [!IMPORTANT]
> **Disabled does not mean impossible to start.** A manual `start`, `restart`,
> another unit's dependency, or deployment automation can still start a
> disabled service. Suspend any old-host deployment or restart automation;
> don't run the installer's service apply on it during recovery. Repeat the
> two checks after any old-host reboot or administrative work.
>
> **Masking** is the stronger systemd setting that refuses service starts.
> If another administrator or automation may start the old services, have
> your agent prepare a reversible mask and verify `masked` and `inactive`
> for both before the replacement starts. These units are regular files in
> `/etc/systemd/system`, so a bare `systemctl mask` can refuse because the
> files already exist. Preserve those exact files privately before a reviewed
> masking change; don't delete them or assume a failed mask worked. Record
> the restoration steps alongside the mask.

If the old server is unreachable but might restart, use its provider controls
to power it off and confirm that state. Disable any provider or external
restart automation for that server and keep it off while you recover. Do not
destroy it yet; its disk may still contain useful recovery information.

**Checkpoint:** you know which backup you will restore, why it is eligible,
and how you have prevented the old app from continuing to write or returning
after a reboot or automated restart. If the last
backup predates a deletion, select a later eligible point. If the source is
lost and eligibility cannot be established from retained deletion and backup
records, keep the restored copy private while investigating. An agent cannot
infer missing deletion history from a backup's timestamp.

## 3. Prepare a new server without creating a new classroom database

**Work here: your provider dashboard and then the replacement server.**
Follow Parts 2 and 3 to create and secure a fresh Ubuntu 22.04 x86-64 server
and verify its SSH fingerprint. In Part 3, select the **same full release SHA
that produced the backup**, rather than upgrading during recovery. Verify
that the source contains the installer fixes required by this handbook.
If the database came from an older installation layout, have your agent map
its paths and release requirements before adapting these commands.

Keep the Cloudflare `A` record pointing at the old server for now. You will
change it after the replacement passes its local checks. Continue using the
same CTH hostname, so your Turnstile and Passwordless registrations still
refer to the intended web address.

Create a **new** installation manifest with Part 4.2. It must contain the
replacement's machine ID and a new installation ID. Set `database` to
`cth_reference`, and `release_sha` to the exact backed-up application SHA.

**Do not run Part 4.3's key-generation block.** The records being restored
belong to the original runtime keys. Step 4 below transfers those keys.
Prepare a valid certificate with Part 4.4 for the same hostname; its DNS TXT
challenge works without moving the web `A` record.

> [!IMPORTANT]
> Copying the old `/etc/cth` directory wholesale would also copy the old
> manifest. That manifest identifies the old machine. Recover the runtime
> file, not the old installation identity, machine ID or installer journal.

## 4. Recover the original runtime file privately

**Work here: a Bash terminal on your computer.** The examples assume the
backup format in Part 7 and an SSH login as root. Replace the IP and archive
filename. A provider that uses another administrator login needs the adaptation
explained in Part 7 before streaming files.

```bash
umask 077
set -o pipefail
cth_recovery_ip=203.0.113.20
cth_key_archive="$HOME/cth-backups/cth-etc-REPLACE.tar.age"
age -d -i "$HOME/cth-backup.agekey" "$cth_key_archive" | tar -tf -
```

Expect a file list including `cth/runtime.env`. Listing names doesn't print
the secret values. Now transfer **only that file**, encrypted through SSH:

```bash
age -d -i "$HOME/cth-backup.agekey" "$cth_key_archive" \
  | tar -xOf - cth/runtime.env \
  | ssh "root@$cth_recovery_ip" \
    'umask 077; set -C; cat > /etc/cth/runtime.env'
```

`tar -xOf` reads one named file from the archive and sends it along the pipe.
It does not unpack the old manifest. `set -C` makes the remote shell refuse to
overwrite an existing file. The backup private key stays on your computer.

If any command fails, stop. A partially transferred runtime file is not usable.
Check the error and the destination privately before retrying; do not solve
it by generating replacement application keys.

**Work here: the replacement server terminal.** Check permissions and run
Part 4.5's configuration validation. It should report `600 root root` and
`manifest and runtime file look valid`. Do not print `runtime.env` into the
conversation. If the old database name differs, update only `DATABASE_URL`
and the new manifest to the same actual database name before enrolling the
host. Preserve all five application keys. These examples use `cth_reference`.

**Checkpoint:** the replacement has its own manifest, the original runtime
keys, a valid certificate and the original application release. The runtime
file has been backed up separately from the database precisely for this job.

## 5. Run the preparation stages, then stop

**Work here: the replacement server terminal as root.** Run the first five
stages from Part 5, checking the success result after each:

```bash
cd /root/cth-installer
manifest=/etc/cth/installation.json
python3 infra/self-hosting/install.py apply host --config "$manifest"
```

Then, one at a time:

```bash
python3 infra/self-hosting/install.py apply postgres --config "$manifest"
```

```bash
python3 infra/self-hosting/install.py apply redis --config "$manifest"
```

```bash
python3 infra/self-hosting/install.py apply release --config "$manifest"
```

```bash
python3 infra/self-hosting/install.py apply config --config "$manifest"
```

Each must finish with `"result": "ok"`. **Do not apply `database`.** That
stage installs a fresh schema; you are about to restore an existing schema.

The installer records preparation through `config`. That record stays true.
It cannot record a restored database through its fresh-install path. Later
steps use a manual continuation and keep their own recovery record; they
must not edit the journal to pretend the remaining install stages ran.

## 6. Restore into the empty replacement database

**Work here: the replacement server terminal.** Confirm the target before
sending it records:

```bash
cd /
runuser -u cthowner -- psql -X -h /var/run/postgresql -p 5432 \
  -d cth_reference -v ON_ERROR_STOP=1 -Atc \
  "SELECT current_database(), current_user, (SELECT count(*) FROM pg_tables WHERE schemaname='public');"
```

Expect `cth_reference|cthowner|0`. The last value must be zero. A failure to
connect or a nonzero table count means this is not the empty target described
by this procedure. Identify the discrepancy before restoring. Do not delete
an existing database to make the check pass.

**Work here: your computer's Bash terminal.** Set the actual database archive
and replacement IP; these variables are separate from the server terminal:

```bash
set -o pipefail
cth_recovery_ip=203.0.113.20
cth_db_archive="$HOME/cth-backups/cth-db-REPLACE.dump.age"
age -d -i "$HOME/cth-backup.agekey" "$cth_db_archive" \
  | ssh "root@$cth_recovery_ip" \
    'cd / && runuser -u cthowner -- /usr/lib/postgresql/14/bin/pg_restore --host=/var/run/postgresql --port=5432 --dbname=cth_reference --exit-on-error --single-transaction --no-owner --no-privileges'
```

This decrypts locally and streams through SSH. The database records never
need a plaintext dump file on your computer. `--single-transaction` makes
PostgreSQL commit only a restore that `pg_restore` completes successfully.
`--no-owner` makes the restored tables and sequences belong to `cthowner`;
`--no-privileges` leaves application permissions for the next step.

**Expected result:** every part of the pipeline succeeds. Immediately run
`echo $?` in your local terminal; it must print `0`. With `pipefail`, a
nonzero result from decryption, SSH or PostgreSQL fails the whole pipeline.
Do this before another command replaces the status.

> [!WARNING]
> A streaming decrypt can report an integrity error after sending data that
> PostgreSQL has already accepted. A failed pipeline therefore leaves an
> **untrusted target**, even if `pg_restore` looked successful. Do not start
> the app or accept the restored records. Preserve both archives and the old
> source, investigate the error and inspect the replacement target before
> choosing a new empty target for another attempt. A transaction is not proof
> that the encrypted archive passed its integrity check.

**Work here: the replacement server.** Read the restored revision and counts:

```bash
cd /
runuser -u cthowner -- psql -X -h /var/run/postgresql -p 5432 \
  -d cth_reference -v ON_ERROR_STOP=1 -Atc \
  'SELECT version_num FROM alembic_version; SELECT count(*) FROM seats; SELECT count(*) FROM classes; SELECT count(*) FROM users;'
```

Compare with the backup's recorded revision and counts, or the backup tool's
manifest if you used that tool. There is no universal correct count. A seat
is one roster place in one class; its count need not equal the user count.
Checking these three counts is a first check, not a row-by-row proof of the
whole restored database.

## 7. Restore the application permissions

**Work here: the replacement server as root.** The database owner can change
its structure. The running app gets narrower permissions: it can work with
classroom records but cannot rewrite migration history or existing audit
events. The following matches this release's fresh-install permission setup:

```bash
cd /
runuser -u postgres -- psql -X -h /var/run/postgresql -p 5432 \
  -d cth_reference -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO cthowner;
GRANT USAGE ON SCHEMA public TO cthapp;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO cthapp;
REVOKE INSERT, UPDATE, DELETE ON public.alembic_version FROM cthapp;
REVOKE UPDATE, DELETE ON public.audit_events FROM cthapp;
GRANT SELECT, USAGE ON ALL SEQUENCES IN SCHEMA public TO cthapp;
GRANT CONNECT ON DATABASE cth_reference TO cthapp;
COMMIT;
SQL
```

These statements grant access; they do not insert or repair classroom records.
Don't extend this to superuser privileges or permissions on future tables.
An agent working with another release must compare its actual permission
setup before adapting it.

The `public` schema—the container holding these tables—may retain the
PostgreSQL administrator as its owner. That is compatible with this layout:
`cthowner` receives explicit permission to create inside it, while `cthapp`
does not. There is no need to grant the app ownership of the schema.

Check the result through the app's own database identity:

```bash
runuser -u cthapp -- psql -X -h /var/run/postgresql -p 5432 \
  -d cth_reference -v ON_ERROR_STOP=1 -Atc \
  "SELECT current_user, has_schema_privilege('public','CREATE'), has_database_privilege(current_database(),'TEMP'), has_table_privilege('public.alembic_version','UPDATE'), has_table_privilege('public.audit_events','UPDATE'), has_table_privilege('public.users','INSERT');"
```

Expect `cthapp|f|f|f|f|t`: app identity, four denied permissions, one allowed
permission. If it differs, compare the actual grants with the source setup.
Do not run the app as the database owner to bypass a permission problem.

## 8. Check which records are allowed to return

If the old source still exists, keep its application disabled and inactive
(or its server powered off except for controlled database reads) and compare its
surviving `users`, `seats` and `classes` identifiers with the restored copy.
Every restored identifier must still exist in the current source. Newer
source records may be absent from an older backup; that is a separate data
loss decision, not permission to recreate deleted identities.

The configurable backup tool performs this comparison when restoring its own
manifest-backed archives; see [backup verification](operations.md#backups-restoration-and-deletion).
Part 7's manual archives don't include that manifest. Use this prompt to have
an agent build the equivalent **read-only** comparison for those archives:

```text
I'm at step 8 of docs/self-hosting/recovery.md. The old app and HTTPS service
are disabled at boot and inactive; the replacement app has not started. Read IDENTITY_QUERIES, identity_sets and missing_identities
in infra/db-backup/cth_db_backup.py at my recorded release. Prepare a read-only
comparison of the old source and restored database for users.id, seats.id,
and classes.class_id. Use explicit old/new SSH hosts and local PostgreSQL
sockets; verify the host and database before reading. Don't print or save the
identifier sets in chat. Report only counts and whether the restored copy
contains any identity absent from the current source. Do not delete rows,
change audit history, or run the tool's scratch-database reset. Explain what
missing newer records mean separately from deleted identities returning.
```

**If the old source is lost:** use retained deletion records and the last
verified post-deletion backup record to establish eligibility. A backup whose
contents and deletion history cannot be reconciled stays offline. Preserve
the evidence and identify the missing fact. Clearing a warning or deleting
suspect rows by hand does not establish a lawful restored database.

**Checkpoint:** the restore's contents, original keys and release agree, and
you have a recorded basis for allowing those identities to return.

Before starting any replacement service, supply the independent expected
baseline paired with this backup and run the `exact` phase of
[the complete audit check](upgrades.md#check-the-complete-audit-history) on the
replacement, using its restored SHA and original audit key. It must match the
saved revision, full scope set, counts, final sequences and head hashes. A
missing or unverified baseline keeps audit completeness unresolved; leave the
service private while recovering that evidence.

## 9. Start and check the replacement using a manual continuation

**Before starting:** confirm again that both old services are disabled and
inactive (or intentionally masked and inactive), or that the old server is
powered off with restart automation disabled. Recheck after any intervening
reboot. Starting the replacement app also starts its timed jobs; there can be work
due since the backup. For a rehearsal, use a fictional-data backup and keep
its hostname restricted.

The fresh-install command cannot advance past a restored database. The block
below calls the same release's runtime functions directly, leaving the fresh
installer journal unchanged. It first checks the new manifest's ownership,
source SHA and machine identity. This is a version-specific recovery technique;
ask your agent to compare the functions before using another release.

**Work here: replacement server, root, `/root/cth-installer`.** Set the action
and step, then run the Python block. Start with these values:

```bash
cd /root/cth-installer
cth_recovery_action=apply
cth_recovery_step=services
```

```bash
python3 -B - "$cth_recovery_action" "$cth_recovery_step" <<'PY'
import os
from pathlib import Path
import sys
sys.path.insert(0, 'infra/self-hosting')
import host, install, runtime
assert os.geteuid() == 0, 'run as server root'
os.environ.clear()
os.environ.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin', LANG='C', LC_ALL='C', DEBIAN_FRONTEND='noninteractive')
path = Path('/etc/cth/installation.json')
install.trusted(path, 0o600)
cfg = install.parse_manifest(path.read_text())
install.trusted(host.ROOT)
host.verify_source(cfg)
assert Path('/etc/machine-id').read_text().strip() == cfg['machine_id'], 'wrong machine'
action, stage = sys.argv[1:]
assert (action, stage) in {('apply', 'services'), ('check', 'scheduler'), ('apply', 'ingress'), ('check', 'readiness')}
os.umask(0o077)
runtime.run(action, stage, cfg)
print('recovery runtime check passed:', stage)
PY
```

Expect `recovery runtime check passed: services`. If it fails, inspect
`systemctl status cth-web.service --no-pager` and the recent journal as in
Part 7.9. Preserve the failure and fix its cause before continuing.

Repeat the Python block for each row below, setting the two variables first.
Do **one row at a time**:

| `cth_recovery_action` | `cth_recovery_step` | What success establishes |
| --- | --- | --- |
| `check` | `scheduler` | Exactly one scheduler owns the replacement database's timed work. |
| `apply` | `ingress` | The dedicated HTTPS front end starts with the matching certificate and private routing. |
| `check` | `readiness` | The running services, local HTTPS, database health, memory protections and scheduler checks pass together. |

Each prints `recovery runtime check passed:` with its step. The ordinary
`install.py check readiness` will still report that the stage hasn't started;
that is the unchanged fresh-install journal, not permission to edit it.
Use the manual readiness check above for this recovered host, and record that
maintenance distinction in your installation note.

## 10. Check the classroom, then move the web address

Before changing DNS, have your agent verify the restored audit chains using
the original `AUDIT_HMAC_KEY`, including the full expected count and head hash.
An audit chain is the tamper-evident record of protected changes. A default
500-event sample or a matching row count is insufficient. Read-only
verification must not create replacement audit events to obtain a pass.
The `exact` phase must have passed before step 9 started the services. Now
run the `extends` phase of [Check the complete audit history](upgrades.md#check-the-complete-audit-history)
using the same independent baseline, restored release and runtime file. This
checks the saved history remains intact while allowing new scheduled work.
Run it again after a permitted test transaction and before reopening.

In Cloudflare, change **only your CTH hostname's existing proxied A record**
to the replacement server's verified IPv4 address. Keep **Proxied** enabled
and **Full (strict)** selected. Leave the Access restriction in place while
you test from your admitted browser.

Now repeat the teacher and student checks in [Part 6](part-6-first-use.md),
using the accounts and classes you expect from the restored backup. Confirm:

- You can sign in, read the correct class and see names correctly. This checks
  the original lookup and encryption keys in addition to database connectivity.
- Teacher TOTP and any passkey you intend to use work at the unchanged hostname.
- A fictional student can sign in, and a separate fictional roster seat can
  complete account setup if you are testing that workflow.
- Balances and history agree with your backup record. Scheduled work since
  startup is accounted for; a difference is explained rather than dismissed.
- The complete audit verification passes after a permitted test transaction.
- A request to the server's direct public address does not bypass the
  Cloudflare-only firewall.

**Checkpoint:** local checks and external browser checks both pass. Record
the recovery time, release, backup, verification results and any known lost
work. Open Access deliberately once those results support reopening.

If a check fails, keep admission restricted. Don't switch the old app back
on while the replacement can write. Once the replacement has accepted new
work, sending users back to an older copy would lose that work; diagnose the
current copy or make an explicit recovery decision with both preserved.

**If you deliberately return to the old server:** first preserve the
replacement's current data and decide how any work since recovery will be
reconciled. On the **replacement**, disable and stop both services with
`systemctl disable --now cth-ingress.service cth-web.service`, then verify
`is-enabled` reports `disabled` twice and `is-active` reports `inactive`
twice, using step 2's commands. Suspend its restart automation too. Only after
that isolation is confirmed may you restore any saved old-host unit files
and remove a deliberate mask, then run
`systemctl enable --now cth-web.service cth-ingress.service` on the **old
server**. This is a deliberate rollback after a data decision, not a general
troubleshooting step. Check the selected server locally and through the
browser before changing DNS or opening admission. The other app stays
disabled and inactive.

## 11. Finish the recovery

Take and test a new database backup and a new `/etc/cth` backup. The latter
must contain the **replacement's** manifest with the **original** application
keys. Update the server IP, new fingerprint and certificate expiry in your
private note. Record the manual runtime-check command from step 9 for future
maintenance on this recovered host.

Retire the old server through [Part 8](part-8-shut-down.md) only after you
have verified the replacement and reconciled its records. Keep your hostname
and the provider integrations now used by the replacement; Part 8's removal
steps apply only to resources you are actually retiring. Reconcile remaining
snapshots and archives with the same deletion rules.

**Agent handoff prompt:**

```text
Summarize this recovery for my private installation note: original release,
old/new host labels, selected backup time, deletion-eligibility evidence,
preparation stages completed, manual continuation steps and verification
results, DNS transition, known data loss and outstanding checks. Record the
old services' disabled/inactive or masked/inactive state, restart automation
changes and any deliberate rollback decision. Include
which readiness command now applies. No secrets, student identifiers or raw
logs. Distinguish checks actually run from checks only described. Identify
remaining billable resources without deleting them.
```

**Return to:** [Part 7: Keep it running](part-7-keep-it-running.md).
