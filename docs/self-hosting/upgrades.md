---
title: "Upgrade your CTH"
category: self-hosting
description: Understand, rehearse and carry out a version change while preserving classroom data and a way back.
roles: [operator]
keywords: [self-hosting, upgrades, migrations, rollback, agents]
---

# Upgrade your CTH

An upgrade replaces the application while keeping your classes and their
records. Sometimes the new version also needs to rearrange the database.
That rearrangement is a **migration**. The tool CTH uses to track migrations
is called **Alembic**; you will see its name in commands and error messages.

You can learn these steps as you go, with an AI agent if you want. The aim is
to make each change small enough that you know what happened and can check it.

> [!NOTE]
> **Procedure status:** this walkthrough follows the current installer's paths,
> service definitions and database roles. The complete upgrade sequence below
> has not been rehearsed on a self-hosted reference server. Rehearse it with
> fictional data first and record the results. Successful project-hosted
> upgrades do not establish that this particular sequence has passed.

## Know which path you are taking

This page covers an installation made with Parts 1–5: Ubuntu 22.04, Python
3.10, PostgreSQL 14, `/etc/cth/runtime.env`, and the `cth-web` service. If you
chose different names, substitute your recorded names throughout. Changing the
operating system or PostgreSQL major version is a separate migration project;
keep those unchanged during this application upgrade.

The initial installer is not an upgrade command. It remembers the original
release and refuses a different one. **Keep `/etc/cth/installation.json` and
`/var/lib/cth-installer` unchanged.** You will record the newer running version
separately rather than rewrite the history of the installation.

| Change | What you need to check |
| --- | --- |
| New application code, same database revision | New dependencies, changed settings, the service's version paths and browser behavior. |
| New code and a newer database revision | All of the above, plus migration order, database permissions and whether the old application can still use the changed database. |
| A failed upgrade | Whether the database changed and whether users or timed jobs have written new records since the change. These determine the way back. |

**Work here:** a root SSH terminal on the server, unless a section says
otherwise. Run each block separately; stop after an error. Variables in this
page disappear when you close the terminal. Re-establish and check them before
continuing in a new session.

## 1. Record what is running

Start with observation. These commands don't change CTH or show its keys:

```bash
systemctl show cth-web.service -p WorkingDirectory -p ExecStart -p FragmentPath -p DropInPaths
runuser -u cthapp -- psql -XAtw -h /var/run/postgresql -p 5432 -d cth_reference \
  -c 'SELECT version_num FROM public.alembic_version'
```

The working directory should be `/opt/cth/releases/` followed by a full
40-character SHA. Save that as **old SHA** and save the database revision.
`FragmentPath` should be `/etc/systemd/system/cth-web.service` and
`DropInPaths` should be empty. A **drop-in** is an extra file that can override
the main service definition; unexpected overrides need investigation before
editing the service.

Set these values to your actual old and chosen new release identifiers:

```bash
old_sha=REPLACE_WITH_OLD_40_CHARACTER_SHA
new_sha=REPLACE_WITH_NEW_40_CHARACTER_SHA
new_tag=vX.Y.Z
```

`old_sha` and `new_sha` identify code versions. They are not passwords. Never
use the word `main` here: it can point at different code tomorrow.

**Checkpoint:** you can name the old code version, its database revision and
the exact new published release. Your old release folder still exists.

## 2. Download the new version beside the old one

Download into a **new** folder. Keeping the old code and its Python libraries
is what makes an application-only rollback possible.

```bash
umask 022
test ! -e "/opt/cth/releases/$new_sha" &&
git clone --no-checkout https://github.com/timwonderer/classroom-token-hub.git "/opt/cth/releases/$new_sha" &&
git -C "/opt/cth/releases/$new_sha" checkout --detach "$new_tag" &&
test "$(git -C "/opt/cth/releases/$new_sha" rev-parse HEAD)" = "$new_sha" &&
git -C "/opt/cth/releases/$new_sha" rev-parse HEAD &&
git -C "/opt/cth/releases/$new_sha" status --porcelain --untracked-files=all
```

The `&&` between commands means “continue only if this succeeded.”
Check the `test` command succeeds before cloning. The SHA must equal
`new_sha`; the status command must print nothing. If the folder already
exists, inspect it rather than delete it or reuse a partially built version.

Read the release notes and compare these files:

```bash
git -C "/opt/cth/releases/$new_sha" diff "$old_sha" "$new_sha" -- \
  requirements.txt migrations/versions migrations/forward_only_register.txt \
  infra/self-hosting/templates/cth-web.service app/__init__.py
```

`diff` shows what changed. Look for new required settings, migration
instructions, changes to startup or service requirements, and newly created
tables or sequences. A **sequence** supplies record numbers in PostgreSQL;
a new one needs its own permission alongside the table it serves. A table
existing is not enough to prove the application can use it.

If the service template changed, compare each change with your installed
unit. Apply its reviewed requirements to the candidate service in step 7;
don't discard existing security settings to make the new version start.

**Agent prompt:**

```text
Help me prepare a CTH upgrade. Read docs/self-hosting/upgrades.md and the
old/new release notes and code at these full SHAs: [old] and [new]. Inspect
the intervening migrations, requirements, startup validation and service
template. Explain the required changes in ordinary language. List the old
and new database revisions, migration order, new settings by NAME ONLY,
new objects requiring permissions, and whether an application-only rollback
is compatible with the changed schema. Cite the actual files. Start
read-only; don't change the running service, database, keys, original
installation manifest or installer journal. Give me the next checkpoint.
```

## 3. Build the new Python environment

CTH's Python libraries live in a **virtual environment**, a folder belonging
to one release. This lets a new version have different libraries without
changing the old one.

The following matches the installer's division of work: the restricted
`cthapp` account installs libraries, then root protects the completed folder.
The destination must not exist. Run from `/`, which `cthapp` can enter:

```bash
cd /
test ! -e "/opt/cth/venvs/$new_sha" &&
install -d -m 0755 -o cthapp -g cthapp "/opt/cth/venvs/$new_sha" &&
runuser -u cthapp -- /usr/bin/python3.10 -m venv "/opt/cth/venvs/$new_sha" &&
runuser -u cthapp -- "/opt/cth/venvs/$new_sha/bin/python" -m pip --isolated install \
  --index-url https://pypi.org/simple --disable-pip-version-check --no-cache-dir \
  -r "/opt/cth/releases/$new_sha/requirements.txt"
```

Stop if a line fails. When installation succeeds:

```bash
chown -R root:root "/opt/cth/venvs/$new_sha"
runuser -u cthapp -- "/opt/cth/venvs/$new_sha/bin/python" -m pip --isolated check
runuser -u cthapp -- "/opt/cth/venvs/$new_sha/bin/gunicorn" --version
```

Expect `No broken requirements found` and a Gunicorn version. Gunicorn is the
program that runs CTH's Flask application. `pip check` checks relationships
between installed libraries; it does not prove every library named by CTH
is present at the requested version. Check those top-level requirements too:

```bash
runuser -u cthapp -- "/opt/cth/venvs/$new_sha/bin/python" - \
  "/opt/cth/releases/$new_sha/requirements.txt" <<'PYTHON'
import importlib.metadata as metadata
import sys
from pathlib import Path
from packaging.requirements import Requirement

for line in Path(sys.argv[1]).read_text().splitlines():
    line = line.split('#')[0].strip()
    if not line:
        continue
    requirement = Requirement(line)
    if requirement.marker is None or requirement.marker.evaluate():
        assert metadata.version(requirement.name) in requirement.specifier, \
            'An installed library does not match the release requirement'
print('All applicable release requirements are installed at matching versions')
PYTHON
```

This follows the current installer's check for its plain requirement lines.
If a later release switches to a different requirements-file format, use its
updated verification rather than removing lines to get past an error.
No service has switched versions yet. If installation failed, leave the old
service alone, inspect the first error and repair the new environment before
continuing.

## 4. Rehearse on a separate copy

Use a private practice server and the [replacement-server procedure](recovery.md)
to restore a practice installation at the **old** release. Use fictional
records and separate provider registrations. Keep your classroom server and
its DNS record unchanged. Stop the practice app before migration so it does
not run payroll while you are comparing records.

On that practice server, repeat steps 1–3, then steps 5–8 below. Write down:

- The before/after database revisions and whether the migration completed.
- The exact settings and permission changes needed, with no secret values.
- Whether both teacher and student sign-in, account claiming and a test
  payroll payment work after the switch.
- Whether the relevant balances and transaction history remain intact.
- Which recovery path you tried and whether it actually restored service.

Use the [release browser procedure](../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-001B_Release_Functional_Browser_Validation.md)
to choose checks for the features the release changes. Confirm the filename
and steps in your selected release if that procedure has moved.

**Checkpoint:** you have tried the version change and a way back on the same
layout before applying it to classroom records. A migration that succeeds as
`cthowner` still needs browser checks as the app's `cthapp` database role.

## 5. Open a maintenance window and take a fresh backup

Arrange a time when your teachers and students won't need the site. Use
[Cloudflare Access maintenance mode](part-7-keep-it-running.md#710-optional-maintenance-mode-with-cloudflare-access)
and verify that an unadmitted browser cannot get through. This keeps new web
requests out; it does not stop timed jobs.

Before stopping services, pause any automation that could restart or deploy
CTH: a scheduled deployment, a provider watchdog, or an agent with an active
restart task. `disable` removes normal boot startup; it does not block an
explicit `systemctl start` from another tool. Inspect your scheduled work and
suspend only the CTH restart/deployment jobs you identify. Record what you
paused so you can restore it after verification. Leave unrelated jobs alone.

On the server, create a private upgrade record and save the **actual boot
settings** before changing them. Boot settings determine whether a service
starts automatically after a reboot; they are separate from whether it is
running right now.

```bash
umask 077
cth_upgrade_record="/root/cth-upgrade-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 0700 "$cth_upgrade_record" &&
cp -p /etc/systemd/system/cth-web.service "$cth_upgrade_record/cth-web.service.before" &&
cp -p /etc/cth/runtime.env "$cth_upgrade_record/runtime.env.before" &&
systemctl show cth-web.service -p UnitFileState --value > "$cth_upgrade_record/cth-web.boot-before" &&
systemctl show cth-ingress.service -p UnitFileState --value > "$cth_upgrade_record/cth-ingress.boot-before"
```

Read those two saved settings:

```bash
cat "$cth_upgrade_record/cth-web.boot-before"
cat "$cth_upgrade_record/cth-ingress.boot-before"
```

The tutorial's normal profile has **`enabled`** for both. If either was
`disabled`, record that deliberate difference; do not later enable it just
because the example profile does. An unexpected value such as `masked`, or
a missing file, needs inspection before you proceed.

Now stop both services **and disable their boot startup**:

```bash
systemctl disable --now cth-ingress.service cth-web.service
systemctl is-enabled cth-ingress.service cth-web.service
systemctl is-active cth-ingress.service cth-web.service
```

Expect `disabled` twice, then `inactive` twice. Those query commands return a
nonzero status for disabled/inactive services; here those are the intended
results. If the connection drops or the server reboots during maintenance,
reconnect and run both queries again before resuming. Both services must
still be disabled and inactive. In your practice rehearsal, include a reboot
at this checkpoint and verify those results after reconnecting. Leave
PostgreSQL running. Check for unexpected application connections:

```bash
runuser -u postgres -- psql -XAtw -d cth_reference \
  -c "SELECT usename, state, count(*) FROM pg_stat_activity WHERE datname = current_database() AND usename IN ('cthapp','cthowner') GROUP BY usename, state"
```

With the app stopped and no other maintenance session connected, expect no
rows. Investigate remaining connections before migrating; don't terminate
unknown work automatically.

Before migrating, [capture the independent expected audit baseline](#save-the-expected-baseline-with-a-recovery-point)
from this stopped source. Keep writers stopped, take the matching backups,
then supply that saved baseline and run the `exact` audit check below. Keep
the encrypted baseline with those recovery files.

On **your computer**, take both backups using [Part 7, sections 7.2–7.4](part-7-keep-it-running.md#72-back-up-the-database)
and verify the restore. Record the old SHA and revision with them.

Continue only when the current backup is usable, the two boot settings are
saved, restart automation is paused and both services remain stopped. A
backup from before a student or class deletion may contain records that
must stay deleted.

## 6. Check and, if necessary, migrate the database

### Prepare any new runtime settings first

Your **runtime file**, `/etc/cth/runtime.env`, holds the settings read when
CTH starts. If the release needs a new setting, add it before invoking its
Flask commands: those commands also load the application configuration.

Use the setting names and formats you identified in step 2. If none changed,
leave the file alone and still run the validation below. Otherwise open the
private file on the server:

```bash
nano /etc/cth/runtime.env
```

Add only the release's required lines, in `NAME=value` format. Save with
**Ctrl+O**, Enter; exit with **Ctrl+X**. For a provider secret, enter it directly
in this private editor. Don't put it in an agent prompt, command argument or
screenshot. Keep the five generated application keys unchanged. Your protected
copy at `$cth_upgrade_record/runtime.env.before` provides the original values
and the configuration return path; it is not a file to share.

Validate using the **new release's** parser, and privately compare the original
application keys with the new file. This prints no key values:

```bash
python3 -B - "$new_sha" "$cth_upgrade_record/runtime.env.before" <<'PYTHON'
import json, re, sys
from pathlib import Path
sha, before_path = sys.argv[1:]
assert re.fullmatch(r'[0-9a-f]{40}', sha), 'Use the full new SHA'
sys.path.insert(0, f'/opt/cth/releases/{sha}/infra/self-hosting')
import runtime
cfg = json.loads(Path('/etc/cth/installation.json').read_text())
cfg['release_sha'] = sha
runtime.trusted(cfg['runtime_env'], secret=True)
current = runtime.parse_env(Path(cfg['runtime_env']).read_text(), cfg)
before = dict(line.split('=', 1) for line in Path(before_path).read_text().splitlines()
              if line and not line.startswith('#'))
for name in ('SECRET_KEY', 'PEPPER_KEY', 'ENCRYPTION_KEY', 'AUDIT_HMAC_KEY',
             'CONFIGURATION_EXPORT_KEY'):
    assert before.get(name) == current.get(name) and current.get(name), \
        'A generated application key changed or is missing; preserve the original'
print('New release runtime format accepted; generated application keys unchanged')
PYTHON
```

**Checkpoint:** the new settings match the release's format and all five
application keys are unchanged. Format validation does not prove a new
provider credential works; the rehearsal's browser checks do that.

If the parser rejects a newly required setting as unknown, compare the new
release's runtime allowlist and its startup requirements. That is a release
configuration mismatch. Keep the app stopped while you resolve the specific
mismatch; don't disable validation, hide the setting in an extra `.env` file,
or modify the old installation record. The upgrade agent prompt in step 2
can produce a release-specific correction and its test.

### Compare the database revisions

The following commands use **systemd**, Ubuntu's service manager, to run
Flask's command-line tool with the private runtime settings. They don't print
the settings. They run as `cthowner`, the database structure owner, rather
than giving the web app permission to change tables.

The web log belongs to `cthapp`, so `cthowner` must use a separate private
log. `LogsDirectory` creates `/var/log/cth-migration` for the transient unit's
user; mode `0700` keeps it private. `/usr/bin/env LOG_FILE=...` changes the
value **inside that command**, after systemd has loaded the runtime file.
This preserves the web log's permissions and the saved runtime settings.
A systemd `Environment=LOG_FILE=...` property would not work here because
`EnvironmentFile` takes precedence over that property.

```bash
systemd-run --wait --pipe --collect \
  -p User=cthowner -p Group=cthowner \
  -p "WorkingDirectory=/opt/cth/releases/$new_sha" \
  -p EnvironmentFile=/etc/cth/runtime.env \
  -p Environment=PYTHONDONTWRITEBYTECODE=1 \
  -p LogsDirectory=cth-migration -p LogsDirectoryMode=0700 -p UMask=0077 \
  /usr/bin/env LOG_FILE=/var/log/cth-migration/app.log \
  "/opt/cth/venvs/$new_sha/bin/flask" --app app db current
```

Then run the same command with `db heads` in place of `db current`. `current`
is the database's revision; `heads` is the revision the new release expects.
There must be exactly one head. The current revision must be the recorded old
revision, and the new migration history must include a path from it.

If both revisions are identical, no database migration is needed. If they
differ and your rehearsal passed, run:

```bash
systemd-run --wait --pipe --collect \
  -p User=cthowner -p Group=cthowner \
  -p "WorkingDirectory=/opt/cth/releases/$new_sha" \
  -p EnvironmentFile=/etc/cth/runtime.env \
  -p Environment=PYTHONDONTWRITEBYTECODE=1 \
  -p LogsDirectory=cth-migration -p LogsDirectoryMode=0700 -p UMask=0077 \
  /usr/bin/env LOG_FILE=/var/log/cth-migration/app.log \
  "/opt/cth/venvs/$new_sha/bin/flask" --app app db upgrade
```

Run `db current` again. It must now equal the single new head. A failed
migration stays a failed migration until you inspect which transaction
committed. Don't run `flask db stamp` to change the revision label: that
changes the label without doing the work.

### Give the application permission to use new objects

The original installer granted permissions on the tables that existed then.
It does not automatically grant access to future tables. Use the exact SQL
prepared and checked in rehearsal, naming each new object explicitly.
For example, **only if the release actually adds these example objects**:

```sql
BEGIN;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.example_table TO cthapp;
GRANT SELECT, USAGE ON SEQUENCE public.example_table_id_seq TO cthapp;
COMMIT;
```

Do not run that example verbatim. A release may need different permissions,
particularly for an audit or policy table. `alembic_version` must remain
read-only to the app; `audit_events` must not gain app UPDATE or DELETE
permissions. Don't grant privileges to all future objects as a shortcut.

**If no new grants are needed, skip creating and executing a permissions
file.** This includes a no-migration release whose required objects and
permissions are unchanged. Record “no new grants required” with the checked
release comparison, then continue to step 7.

If new grants are needed, save the reviewed release-specific SQL in a private
root-owned file, then apply it as the structure owner:

```bash
runuser -u cthowner -- psql -Xw -v ON_ERROR_STOP=1 \
  -h /var/run/postgresql -p 5432 -d cth_reference < /root/cth-upgrade-permissions.sql
```

**Agent prompt for this checkpoint:**

```text
For the upgrade from [old SHA] to [new SHA], inspect only the intervening
migrations and their application callers. Produce exact SQL granting cthapp
the permissions each new table/sequence needs; explain each grant. Preserve
read-only alembic_version, append-only audit_events, and existing policy
protections. Identify renamed objects and data migrations too. Show how to
test the app role's permissions on an isolated restored database. Do not
apply the SQL to my live database until the rehearsal's results are recorded.
If no objects require new grants, show the evidence and say so.
```

## 7. Switch the service to the new code

Make a candidate copy, then change only its old SHA paths to the new ones:

```bash
mkdir -m 0700 "$cth_upgrade_record/candidate"
cp -p /etc/systemd/system/cth-web.service "$cth_upgrade_record/candidate/cth-web.service"
nano "$cth_upgrade_record/candidate/cth-web.service"
```

`nano` is a text editor. Change the release directory in `WorkingDirectory`,
and both SHA paths in `ExecStart`. Save with **Ctrl+O**, Enter; exit with
**Ctrl+X**. If step 2 found service-template changes, include the reviewed
changes you already tested in rehearsal. Compare before installing:

```bash
diff -u "$cth_upgrade_record/cth-web.service.before" "$cth_upgrade_record/candidate/cth-web.service"
systemd-analyze verify "$cth_upgrade_record/candidate/cth-web.service"
```

`diff` returns status 1 when files differ; that is expected. Check the actual
changes. The candidate must keep the restricted account, environment-file
path, loopback bind, scheduler configuration and service hardening. The candidate keeps the real unit filename so systemd can validate it.
A verification error is a reason to fix the candidate before replacing the
installed file.

Install the verified candidate, reload the service definitions and start CTH:

```bash
install -m 0644 "$cth_upgrade_record/candidate/cth-web.service" /etc/systemd/system/cth-web.service &&
systemctl daemon-reload &&
systemctl start cth-web.service &&
systemctl status cth-web.service --no-pager &&
curl --fail --show-error --silent http://127.0.0.1:8000/health
```

Expect `active (running)` and `ok`. Starting CTH also starts its scheduler;
the maintenance gate does not freeze timed work. Note the restart time.

If startup fails, inspect `journalctl -u cth-web.service -n 50 --no-pager`
privately. A `permission denied for table` points back to the reviewed grants;
a missing setting points back to release configuration. Preserve existing
keys when adding settings. Don't regenerate the runtime file.

## 8. Verify before reopening

Start the front end while the Cloudflare maintenance gate remains in place:

```bash
systemctl start cth-ingress.service
systemctl show cth-web.service -p WorkingDirectory -p ExecStart
```

Both paths must now name `new_sha`. Check the database revision, service
status and certificate as in Parts 6 and 7. Check the scheduler's current
startup messages:

```bash
journalctl -u cth-web.service -b --no-pager --reverse \
  --grep='Scheduler started in pid' -n 1
```

A matching line is useful evidence, but alone doesn't prove there is exactly
one current scheduler owner. To run the selected release's scheduler, local
HTTPS, storage and service-readiness checks without changing the original
installation record, use its internal check function with the new SHA held
only in memory:

```bash
python3 -B - "$new_sha" <<'PY'
import json, re, sys
from pathlib import Path
sha = sys.argv[1]
assert re.fullmatch(r'[0-9a-f]{40}', sha), 'Use the full new SHA'
sys.path.insert(0, f'/opt/cth/releases/{sha}/infra/self-hosting')
import runtime
cfg = json.loads(Path('/etc/cth/installation.json').read_text())
cfg['release_sha'] = sha
runtime.run('check', 'readiness', cfg)
print('New runtime readiness checks passed; original installer record unchanged')
PY
```

This uses an internal Python interface, not a new installer command. Compare
`runtime.py` in the selected release before using it if that interface has
changed. The initial installer `check services` compares against the original
unit byte for byte and will no longer describe this upgraded service; don't
edit its journal to remove that disagreement.

In an admitted browser, repeat teacher/student sign-in and the release's
chosen browser checks. Use a fictional practice class for test payments;
inspect real classroom history read-only. Compare recorded balances and
history, explaining changes due to timed jobs or the release itself. Verify
protected audit history with the `extends` phase of
[the complete-chain check below](#check-the-complete-audit-history), using the
baseline saved before migration.
An `ok` health response confirms a database connection, not financial correctness.

**Reopen only when** the running paths and database revision agree with the
plan, service and scheduler checks pass, expected browser behavior works,
and differences in records are understood. Only now restore the intended
boot startup settings recorded in step 5. Run these cases individually and
stop if either reports an unexpected or missing saved setting:

```bash
case "$(cat "$cth_upgrade_record/cth-web.boot-before")" in
  enabled) systemctl enable cth-web.service ;;
  disabled) systemctl disable cth-web.service ;;
  *) printf '%s\n' 'Inspect the saved web boot setting before proceeding' >&2; false ;;
esac
```

```bash
case "$(cat "$cth_upgrade_record/cth-ingress.boot-before")" in
  enabled) systemctl enable cth-ingress.service ;;
  disabled) systemctl disable cth-ingress.service ;;
  *) printf '%s\n' 'Inspect the saved ingress boot setting before proceeding' >&2; false ;;
esac
```

Check `systemctl is-enabled cth-web.service cth-ingress.service` against those
two saved values, and check that both services are currently active. Restoring
boot startup does not itself start a stopped service. Deliberately starting
`cth-web` starts its timed jobs, so repeat runtime and browser checks after
any intervening reboot or stop rather than assuming the earlier checks still
apply.

Restore the recorded restart/deployment automation only after it is configured
for the verified new version. Then remove maintenance mode and check from an
ordinary student session. Record the new SHA, revision, restart time, backup
filenames, boot settings, restored automation, changed settings by name,
checks and any remaining issue. Keep the old release and protected backup
until their retention decision.

## Check the complete audit history

CTH keeps a signed history of protected changes. Its **chain head** records
where a chain should end. Checking only the restored chains against their own
restored heads can miss an entire chain that disappeared with its head, or
history shortened consistently at both places. Recovery needs an
**independent expected baseline**: the scopes, event counts, sequence numbers
and head hashes recorded from the trusted source at that recovery point.

The baseline stays private and encrypted alongside your backups. It is not
sent to the project. Never create the expected baseline from the restored
copy you are trying to verify.

### Save the expected baseline with a recovery point

Do this while **all application writers are disabled and stopped**, before
taking the matching database backup in the same maintenance window. The
upgrade's step 5 and recovery's step 2 explain how to stop writers safely.
Keep them stopped until both capture and backup have succeeded; otherwise
those files may describe different moments. Pause other administrative
writes too. A live dump's ordinary table-count manifest does not contain
this independent audit baseline.

**Work here: your computer, Bash.** Replace the source IP and `age1…` recipient.
This reads the trusted source over SSH and encrypts the expected metadata
locally. It prints only the encrypted filename and size:

```bash
umask 077
set -o pipefail
set -o noclobber
mkdir -p "$HOME/cth-backups"
chmod 700 "$HOME/cth-backups"
cd "$HOME/cth-backups"
cth_audit_baseline="cth-audit-$(date -u +%Y%m%dT%H%M%SZ).json.age"
if ssh root@203.0.113.10 'cd / && runuser -u postgres -- psql -XqAtw -h /var/run/postgresql -p 5432 -d cth_reference -v ON_ERROR_STOP=1' <<'SQL' \
  | age -r age1… > "$cth_audit_baseline.partial"
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT jsonb_build_object(
  'format', 1,
  'alembic_revision', (SELECT version_num FROM public.alembic_version),
  'heads', COALESCE(jsonb_agg(jsonb_build_object(
    'chain_scope', chain_scope, 'event_count', event_count,
    'latest_sequence', latest_sequence, 'latest_hash', latest_hash
  ) ORDER BY chain_scope), '[]'::jsonb)
) FROM public.chain_heads;
COMMIT;
SQL
then
  mv "$cth_audit_baseline.partial" "$cth_audit_baseline"
  ls -lh "$cth_audit_baseline"
else
  echo 'Audit baseline capture failed; keep writers stopped and inspect the error.' >&2
  false
fi
```

A `.partial` file is not a completed baseline. After success, take the
matching database and key backups from Part 7 without restarting writers.
Record all three filenames, the source SHA and the recovery time together.
Keep the baseline off the server as well as on protected storage. If capture
or a dump fails, keep the source intact and repeat the matched set while it
is still stopped; don't label files from different points as one set.

### Supply the saved baseline for verification

**Work here: your computer, Bash.** Select the baseline paired with the
particular backup or pre-upgrade state, then send it to the server being
checked. During recovery, this is the **replacement's** IP. The file is
plaintext only inside the protected SSH stream and on that server:

```bash
set -o pipefail
cth_saved_audit="$HOME/cth-backups/cth-audit-REPLACE.json.age"
age -d -i "$HOME/cth-backup.agekey" "$cth_saved_audit" \
  | ssh root@203.0.113.20 \
    'umask 077; set -C; cat > /etc/cth/audit-baseline.expected.json'
```

Immediately run `echo $?`; it must be **0**. A failed transfer or decryption
can leave a partial file: do not use it as evidence. Inspect the cause before
retrying. The remote shell refuses to overwrite an existing expected file;
identify which recovery point it belongs to before replacing it. Never print
its contents into chat or a public report.

**Work here: server as root.** Choose the comparison you need:

| Phase | When to use it | What must match |
| --- | --- | --- |
| `exact` | Restored database **before any app or scheduler starts**, or the frozen source before an upgrade. | The recorded revision and exact set of scopes, counts, final sequences and hashes must match the saved baseline. |
| `extends` | After the app starts and may append legitimate new events. | Every saved scope and its complete saved history must remain. The event at each saved final sequence must match its saved hash; the complete current chains must also verify. New events don't erase the saved expectations. |

Run `exact` first on a recovery target. A later `extends` pass does not replace
that check. For an upgrade, verify `exact` before migration and `extends`
after startup; check the new database revision separately in step 6.
If the source is lost and no trusted expected baseline survives, record
**audit completeness unverified** and keep the recovered service private
while locating the evidence. Don't substitute its own restored head values.

The command below uses the currently selected release and original audit key.
`LoadCredential` lets systemd supply the root-owned expected file privately
to this one command. Its separate private log also works on a replacement
where the web service has not yet created its own log directory. The
transaction is read-only and sees one consistent database view.

`--pipe` passes the Python block through standard input; `--wait` returns its
exit status. Paste the complete block including `PYTHON`; do not add `--pty`.
See the [systemd 249 command reference](https://www.freedesktop.org/software/systemd/man/249/systemd-run.html#--pipe).
Importing this release's Flask app does not start its scheduler.

```bash
cth_audit_sha=REPLACE_WITH_SELECTED_40_CHARACTER_SHA
cth_audit_phase=exact
systemd-run --wait --pipe --collect \
  -p User=cthapp -p Group=cthapp \
  -p "WorkingDirectory=/opt/cth/releases/$cth_audit_sha" \
  -p EnvironmentFile=/etc/cth/runtime.env \
  -p Environment=PYTHONDONTWRITEBYTECODE=1 \
  -p LoadCredential=cth-audit-baseline:/etc/cth/audit-baseline.expected.json \
  -p LogsDirectory=cth-audit-check -p LogsDirectoryMode=0700 -p UMask=0077 \
  /usr/bin/env LOG_FILE=/var/log/cth-audit-check/app.log \
  "/opt/cth/venvs/$cth_audit_sha/bin/python" - "$cth_audit_phase" <<'PYTHON'
import json, os, sys
from pathlib import Path
from sqlalchemy import text
from app import create_app
from app.extensions import db
from app.models import AuditEvent, ChainHead, ClassEconomy, Transaction
from app.utils.audit_verifier import verify_chain, verify_row_lineage


def compare_expected_heads(expected, current, anchors, phase):
    assert phase in {'exact', 'extends'}, 'Choose exact or extends'
    saved = {row['chain_scope']: row for row in expected}
    actual = {row['chain_scope']: row for row in current}
    assert len(saved) == len(expected), 'Duplicate scopes in expected baseline'
    assert set(saved) <= set(actual), 'An expected audit chain is missing'
    if phase == 'exact':
        assert saved == actual, 'Restored audit heads differ from expected baseline'
    for scope, row in saved.items():
        assert row['event_count'] == row['latest_sequence'] >= 0, 'Invalid expected count'
        assert actual[scope]['event_count'] >= row['event_count'], 'Audit history is shorter than expected'
        assert actual[scope]['latest_sequence'] >= row['latest_sequence'], 'Audit sequence is shorter than expected'
        assert anchors.get(scope) == row['latest_hash'], 'Saved audit head hash no longer matches'


phase = sys.argv[1]
baseline = json.loads((Path(os.environ['CREDENTIALS_DIRECTORY']) /
                       'cth-audit-baseline').read_text())
assert baseline['format'] == 1, 'Unknown expected-baseline format'
assert baseline['heads'], 'Expected baseline contains no audit scopes'
app = create_app()
with app.app_context():
    db.session.execute(text(
        'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
    if phase == 'exact':
        revision = db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
        assert revision == baseline['alembic_revision'], 'Recovery-point revision differs'
    heads = ChainHead.query.all()
    current = [dict(chain_scope=h.chain_scope, event_count=h.event_count,
                    latest_sequence=h.latest_sequence, latest_hash=h.latest_hash)
               for h in heads]
    event_scopes = {scope for scope, in db.session.query(AuditEvent.chain_scope).distinct().all()}
    assert event_scopes <= {h.chain_scope for h in heads}, 'Events have a missing head'
    anchors = {}
    for saved in baseline['heads']:
        if saved['latest_sequence'] == 0:
            anchors[saved['chain_scope']] = 'genesis'
        else:
            event = AuditEvent.query.filter_by(chain_scope=saved['chain_scope'],
                sequence_number=saved['latest_sequence']).one_or_none()
            anchors[saved['chain_scope']] = event.event_hash if event else None
    compare_expected_heads(baseline['heads'], current, anchors, phase)
    nonempty = 0
    for head in heads:
        count = AuditEvent.query.filter_by(chain_scope=head.chain_scope).count()
        result = verify_chain(head.chain_scope, limit=count + 1)
        assert result.state == 'VERIFIED', 'Audit chain verification failed'
        assert result.event_count == count == head.event_count == head.latest_sequence, \
            'Audit count or final sequence differs'
        assert result.last_good_hash == head.latest_hash, 'Audit final hash differs'
        nonempty += bool(count)
    checked_rows = 0
    for classroom in ClassEconomy.query.all():
        row = Transaction.query.filter_by(class_id=classroom.class_id).filter(
            Transaction.lineage_event_id.isnot(None)).order_by(Transaction.id.desc()).first()
        if row is not None:
            result = verify_row_lineage('ledger_transaction', row.id, row)
            assert result.state == 'VERIFIED', 'Protected ledger row check failed'
            checked_rows += 1
    db.session.rollback()
    assert nonempty > 0 and checked_rows > 0, 'No protected financial activity to verify'
    print(f'Expected-baseline comparison passed: {phase}')
    print(f'Complete nonempty chains checked: {nonempty}; protected ledger rows checked: {checked_rows}')
PYTHON
```

Expect `Expected-baseline comparison passed:` with the chosen phase and
positive verification counts, with no assertion or command failure. This
checks all retained chains and one selected protected ledger row per class;
it doesn't verify every business record or every balance calculation. Use a
real permitted payment in your fictional practice class before the first
backup so there is protected financial activity to verify.

After startup, set `cth_audit_phase=extends` and run the Python command again.
Explain new events using actual scheduler or browser activity. A retired
signature format or missing expected record is unresolved evidence, not a
reason to rewrite history. Preserve the original audit key, events and heads
on any failure. See [audit lineage integrity](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md).

## If the upgrade fails: choose the way back

**Rollback** means returning to a working earlier state. It does not always
mean running the migrations backward.

| What happened | Your next action |
| --- | --- |
| New version never started and no database change committed | Restore the saved unit and start the old version. |
| Database changed but the old application is explicitly compatible with it | Return the service to the old version; retain the changed database. Use the compatibility result from rehearsal. |
| Database changed incompatibly | Keep the site restricted. Use a verified eligible pre-upgrade backup on a replacement target, or a reviewed forward fix. |
| Users or scheduled jobs wrote new records after the upgrade | Identify those records before choosing a restore. A pre-upgrade backup omits them. |
| Whether the database changed is unclear | Inspect its revision and migration output while the app stays stopped. Don't guess based on the last line of output. |

For an application-only return, after confirming database compatibility:

```bash
systemctl disable --now cth-ingress.service cth-web.service &&
install -m 0600 "$cth_upgrade_record/runtime.env.before" /etc/cth/runtime.env &&
install -m 0644 "$cth_upgrade_record/cth-web.service.before" /etc/systemd/system/cth-web.service &&
systemctl daemon-reload &&
systemctl start cth-web.service &&
curl --fail --show-error --silent http://127.0.0.1:8000/health
```

Keep restart/deployment automation paused during this return. The explicit
`start` above starts the old version's scheduler too; note the time and check
any timed activity. The services remain disabled for boot startup while you
verify the old runtime and database together. Restart ingress, then repeat
readiness, audit and browser checks behind the gate.

Only after that deliberate return passes, follow step 8's boot-setting
restoration cases using the same saved settings. Restore automation for the
verified **old** version, then reopen. If verification fails, disable and stop
both services again; after any reboot, confirm disabled/inactive state before
resuming investigation. Restoring the files does not roll back a database
or recover a deleted key.

For a database return, follow [replacement-server recovery](recovery.md) using
the eligible backup and its matching old code and keys. Do not restore over
the only live database. Migrations listed in
`migrations/forward_only_register.txt` cannot be undone by a normal downgrade.
Even an apparently reversible migration needs a rehearsed explicit target
revision; this guide does not prescribe an automatic downgrade.

**Agent prompt after a failure:**

```text
My CTH upgrade stopped at [step]. The old SHA/revision were [values]; the new
SHA/revision were [values]. Here is the redacted error. First inspect the
running unit, service state and actual database revision read-only. Establish
whether a migration committed and whether web users or the scheduler wrote
records since restart. Compare the old app's schema compatibility. Give me
an application-only return, forward repair or isolated restore plan with
expected checks and possible data loss. Do not stamp a revision, rewrite
audit history, downgrade blindly, restore over live data or alter the original
installer journal. Explain what evidence remains missing.
```

**Back to:** [Part 7: Keep it running](part-7-keep-it-running.md#78-upgrading-cth-and-rolling-back)
