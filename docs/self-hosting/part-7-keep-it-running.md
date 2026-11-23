---
title: "Part 7: Keep it running"
category: self-hosting
description: Encrypted backups with a test restore, certificate renewal, system updates, upgrades and logs for a self-hosted Classroom Token Hub.
roles: [operator]
keywords: [self-hosting, tutorial, backup, restore, age, certificate renewal, upgrade, logs]
---

# Part 7: Keep it running

Once setup is finished, your work becomes a small routine. You don't need to
keep a terminal open all day. You do need to know when your last usable backup
was made, when the certificate expires and whether the site still works.

| When | Job | Where to go |
| --- | --- | --- |
| Before real students join | Create encrypted backups and restore a copy. | 7.1–7.4 |
| On your chosen backup schedule, and after deletions or settings changes | Make and check the appropriate new backups. | 7.2, 7.3 and 7.5 |
| Before the certificate's recorded expiry | Renew it and test HTTPS. | 7.6 |
| When Ubuntu updates or asks for a reboot | Check updates, reboot when appropriate and verify the app. | 7.7 |
| When a CTH release is available | Read what changed, rehearse and choose an upgrade window. | 7.8 and the [upgrade walkthrough](upgrades.md) |
| If the server is lost | Restore matching data and keys onto a replacement. | [Recovery walkthrough](recovery.md) |
| When a user reports a problem | Check the relevant service and browser workflow. | 7.9 and [Troubleshooting](troubleshooting.md) |

The sections below explain the backup commands in detail. Work through each
check once with practice data so those commands aren't new during an outage.

Set up backups **before** real students join. Test a restore so you know the
archive and its decryption key work together.

The backup commands run on **your computer** in a macOS or Linux terminal. On
Windows, use [WSL](https://learn.microsoft.com/windows/wsl/install). These are
Bash commands, not PowerShell commands. Run `bash` in your local terminal
before following this part, and use a normal local user, not root.

Test SSH from this terminal first. If your provider uses `ubuntu` rather than
`root`, the remote commands below also need that login and an authorized
noninteractive `sudo` arrangement. This means permission to run the specific
remote backup commands without a password prompt inside the data stream.
Use the [agent prompt below](#adapting-these-commands-to-your-computer) to
work out that arrangement for your provider. Do not add `ssh -t` to get a
prompt: it changes the connection to a terminal and can corrupt a binary dump.

Replace `203.0.113.10` with your server's IP address throughout.

## Adapting these commands to your computer

If the tools or login differ from the examples, use this before changing them:

```text
Help me prepare Part 7 of docs/self-hosting on [my OS]. Inspect existing age,
SSH and PostgreSQL tools first. Identify their paths and versions without
changing any existing database service. These Bash commands belong on my
computer; the quoted command after ssh belongs on my server.

My server login is [root / ubuntu / other]. If it isn't root, derive narrowly
scoped noninteractive sudo commands for pg_dump and the protected /etc/cth
archive from my provider's configuration. Show the exact changes and verify
sudo -n can run those commands before streaming any backup. Don't grant
unrestricted passwordless sudo or use ssh -t for binary data. Keep SSH host
fingerprint verification enabled. Explain each adaptation and its check.
```

The two keys in this chapter have different jobs. CTH's **application keys**
let the app use its records. Your **age private key** opens the encrypted
backup archives. Recovery needs both: the age key opens the saved files, and
the saved application keys let CTH read and use the restored data.

## 7.1 Make a backup key

**What you're doing.** Creating a key pair that encrypts your backups.

**Why.** Backups hold student names and every classroom record. Encrypting
them on the way to your computer means a lost laptop or a synced folder
doesn't expose them. The private half of the key never goes near the server.

**Steps.**

1. Install [age](https://github.com/FiloSottile/age#installation)
   (macOS with Homebrew: `brew install age`; Ubuntu or WSL: `sudo apt install age`).
2. Create the key:

   ```bash
   umask 077
   age-keygen -o ~/cth-backup.agekey
   ```

3. Save the file `~/cth-backup.agekey` in your password manager as an
   attachment, or copy it to a USB stick you keep somewhere safe.

Add to your note: the **public key** printed by `age-keygen` (it starts `age1`).

**What you should see.** `Public key: age1…`.

**If something looks wrong.** If you lose `cth-backup.agekey`, every backup made
with it is unreadable. Keep two copies in different places.

## 7.2 Back up the database

**What you're doing.** Copying the whole database from the server, encrypted,
into a file on your computer.

**Why.** The database holds accounts, classes, balances and history. It does
not contain the application keys; back those up separately in 7.3.

**Before copying:** the next block reads the database on the server. It
writes the encrypted result to **your computer**. The `pg_dump` command creates
a consistent database copy while the app runs; it doesn't stop teaching or
replace the live database. A **dump** is PostgreSQL's name for that saved copy.

**Steps.** In each backup session, use a private local folder and replace
`age1…` with your public key. Choose a new filename for each attempt:

```bash
umask 077
set -o pipefail
set -o noclobber
mkdir -p "$HOME/cth-backups"
chmod 700 "$HOME/cth-backups"
cd "$HOME/cth-backups"
backup="cth-db-$(date -u +%Y%m%dT%H%M%SZ).dump.age"
ssh root@203.0.113.10 'cd / && runuser -u postgres -- pg_dump --format=custom cth_reference' \
  | age -r age1… > "$backup.partial" \
  && mv "$backup.partial" "$backup" && ls -lh "$backup"
```

`set -o pipefail` makes the whole command fail if *any* part fails, not just
the last one. Without it, a dropped connection or a failed `pg_dump` still
leaves an encrypted file that looks fine but holds nothing useful. The backup
is written to a `.partial` file first and only gets its real name once
everything succeeded, so a failed run never replaces a good backup.

**What you should see.** No output from the dump, then one line from `ls`
showing the saved filename and size. Size alone does not prove the archive
is complete; the restore test in 7.4 does that check. Save the release SHA
with your backup record. Avoid class or account deletions during a backup;
if one occurs, retire that archive and take a new one afterwards.

For a recovery point you will use to reopen the site, also
[save an independent audit baseline](upgrades.md#save-the-expected-baseline-with-a-recovery-point)
while all writers are paused, and take the matching dump in that same stopped
window. The baseline lets recovery detect a completely missing or shortened
audit chain. A live database dump remains useful, but by itself supplies no
independent expected head values. Keep the baseline, database archive and key
archive paired in your private backup record.

**If something looks wrong.** If there's no `ls` line, the backup failed: read
the error, and delete the leftover `.partial` file. Check you used the right IP
address and the database name `cth_reference`.

## 7.3 Back up the keys and settings

**What you're doing.** Copying `/etc/cth` (the manifest, the runtime file
and the certificate) the same way.

**Why.** The database backup is useless without the keys in the runtime file.
`ENCRYPTION_KEY` decrypts student names; `PEPPER_KEY` is needed for anyone to
sign in. They exist only on the server until you copy them.

**Steps.**

```bash
umask 077
set -o pipefail
set -o noclobber
mkdir -p "$HOME/cth-backups"
chmod 700 "$HOME/cth-backups"
cd "$HOME/cth-backups"
backup="cth-etc-$(date -u +%Y%m%dT%H%M%SZ).tar.age"
ssh root@203.0.113.10 'tar -C /etc -cf - cth' \
  | age -r age1… > "$backup.partial" \
  && mv "$backup.partial" "$backup" && ls -lh "$backup"
```

**What you should see.** One line from `ls` showing a small file, a few kilobytes.

**If something looks wrong.** As in 7.2, no `ls` line means the backup failed:
read the error, and delete the leftover `.partial` file.

> [!IMPORTANT]
> Take a new copy whenever `/etc/cth` changes, including certificate renewal.
> Keep the matching key archive for every eligible database backup. The
> `AUDIT_HMAC_KEY` is also needed to verify the audit history. Store a protected
> off-device copy of the encrypted archives, separate from the age private
> key; losing your computer must not lose both the data and its only key.

## 7.4 Test that a backup restores

**What you're doing.** Restoring a database backup into a throwaway database
on your computer, and checking the data is there.

**Why.** It proves your backup file and your key both work. Do this after your
first backup and every few months after.

**Before copying:** a **restore** loads a saved database into PostgreSQL.
This drill uses a new, temporary PostgreSQL instance on your computer. That
keeps the restored copy separate from the classroom server and any databases
you already have. A **socket** is the private local connection used to reach
that instance; there is no internet-facing database connection here.

**Steps.** Run each block separately and stop on any error. Keep this terminal
open until cleanup, because later commands use its variables. Use the
**total seat count across all classes at the backup's recovery point** as
your expectation—not the current roster or just one class. Every roster entry
counts as a seat, claimed or unclaimed. For example, two classes with 10 and
12 roster entries should restore as 22 seats.

For a first practice run, record that total when taking the backup and keep
the practice roster unchanged during capture. A manifest-backed backup from
the [configurable backup tool](operations.md#backups-restoration-and-deletion)
records `table_counts.seats` from the same database snapshot as its dump. If
an older manual backup has no trustworthy recorded total, mark the seat-count
comparison **unverified**; a difference from today's roster does not establish
that the backup is faulty. Use a new eligible, recorded backup to complete
that comparison.

1. Install PostgreSQL **14 server and client tools**. On macOS with Homebrew:

   ```bash
   brew install postgresql@14
   export PATH="$(brew --prefix postgresql@14)/bin:$PATH"
   ```

   On Ubuntu/WSL, install `postgresql-14` from the
   [PostgreSQL apt repository](https://www.postgresql.org/download/linux/ubuntu/),
   then run `export PATH="/usr/lib/postgresql/14/bin:$PATH"`.
   Do not start a shared Homebrew service for this drill. We create a separate
   instance below. Confirm `initdb --version` and `pg_restore --version` both
   report 14. The source dump is made by PostgreSQL 14; matching tools keep
   this drill consistent with the installer. This does not extend version
   14's [support lifetime](before-you-begin.md#which-release-this-guide-matches).

2. Create an empty, private instance. It has no TCP listener and uses a new
   local socket directory, so it cannot connect to your normal database:

   ```bash
   umask 077
   set -o pipefail
   unset PGHOST PGHOSTADDR PGPORT PGDATABASE PGUSER PGPASSWORD PGSERVICE PGSERVICEFILE PGOPTIONS
   cth_restore_dir=$(mktemp -d /tmp/cth-restore.XXXXXX) &&
   mkdir "$cth_restore_dir/socket" &&
   initdb -D "$cth_restore_dir/data" --username=cth_restore_operator --auth=trust --encoding=UTF8 --locale=C &&
   pg_ctl -D "$cth_restore_dir/data" -l "$cth_restore_dir/server.log" \
     -o "-c listen_addresses='' -k '$cth_restore_dir/socket' -p 55434" -w start &&
   export PGHOST="$cth_restore_dir/socket" PGPORT=55434 PGUSER=cth_restore_operator &&
   psql -X -d postgres -v ON_ERROR_STOP=1 -Atc 'SHOW data_directory'
   ```

   The last line must print the new directory ending in `/data`. Stop if it
   does not. The temporary `trust` authentication is confined to this private
   local directory; never use it for the classroom server.

3. Set the two archive paths to your actual filenames, then restore:

   ```bash
   : "${PGHOST:?Complete step 2 in this terminal before restoring}"
   cth_db_archive="$HOME/cth-backups/cth-db-REPLACE.dump.age"
   cth_key_archive="$HOME/cth-backups/cth-etc-REPLACE.tar.age"
   createdb cth_restore_test && \
     age -d -i "$HOME/cth-backup.agekey" "$cth_db_archive" \
       | pg_restore --exit-on-error --single-transaction --no-owner --no-privileges --dbname=cth_restore_test
   ```

   Continue only if this succeeds. `--no-owner --no-privileges` avoids
   requiring the server's roles on your computer. The restore stops on errors
   and commits only a complete successful transaction. See
   [PostgreSQL's restore options](https://www.postgresql.org/docs/14/app-pgrestore.html).

4. Check the restored revision, seats and key archive:

   ```bash
   psql -X -d cth_restore_test -v ON_ERROR_STOP=1 -Atc 'SELECT version_num FROM alembic_version'
   psql -X -d cth_restore_test -v ON_ERROR_STOP=1 -Atc 'SELECT count(*) FROM seats'
   age -d -i "$HOME/cth-backup.agekey" "$cth_key_archive" | tar -tf -
   ```

   Compare the revision with the installed release's database baseline in
   `migrations/fresh/<revision>/manifest.json`. Compare the seat count with the
   all-class total recorded for that backup's recovery point; there is no
   universal expected count. The file list must include
   `cth/runtime.env` and `cth/installation.json`. Do not print their contents.

5. After checking the results, stop the temporary instance and remove its
   restored data. Confirm the printed path is this drill's `/tmp/cth-restore.…`
   directory before running the second block:

   ```bash
   printf '%s\n' "$cth_restore_dir"
   pg_ctl -D "$cth_restore_dir/data" -m fast -w stop
   ```

   Only after shutdown succeeds:

   ```bash
   rm -r -- "$cth_restore_dir"
   unset PGHOST PGPORT PGUSER cth_restore_dir cth_db_archive cth_key_archive
   ```

   Do this cleanup after a failed drill too, once you have inspected the error.
   The temporary database contains real records when you test a real backup.

**What you should see.** A successful restore, the expected revision and seat
count, the key archive's file list, and a clean shutdown. An error at any step
means the drill has not passed; keep the source and encrypted archives intact.

**If something looks wrong.**

- **`no identity matched any of the recipients`:** the archive and age private
  key do not match.
- **`createdb` fails:** stop. Do not restore into an existing database or run
  `dropdb` to clear the error.
- **`unsupported version` from `pg_restore`:** inspect which executable is
  running (`command -v pg_restore`) and its version. Do not retry against a
  different server to get past the error.
- **The terminal closed:** do not rerun the restore with missing variables.
  Locate this drill's private directory and stop its instance with `pg_ctl -D`
  before cleaning it up. Never substitute the system PostgreSQL data directory.

**What has already been proven.** The production release procedure uses the
same PostgreSQL dump/restore and age encryption tools. Its
[v2.4.5 record](https://github.com/timwonderer/classroom-token-hub/blob/main/docs/ops/audits/DEPLOY_2026-11-14_1d74ea8.md)
reports a successful restore with matching manifest, revision and table
counts, plus a successful check that no deleted identities would return.
Those results remain evidence for that procedure and its prerequisites.

This chapter's manual commands are a smaller drill: they check archive
readability, the restored revision and the seat count. They do not produce the
production tool's manifest or automate its deleted-identity check. For those
checks, use the [configurable backup tool](operations.md#backups-restoration-and-deletion).
Do not run the production wrapper unchanged; its host and service are different.

A database restore is one part of bringing a **replacement server** online.
The [recovery walkthrough](recovery.md) continues through restoring the
application keys, rebuilding permissions, starting the services and changing
DNS. Practice that whole route with fictional data, too. The local drill
above proves archive readability and basic restored data; it doesn't by itself
prove the replacement site is ready for students.

**Agent prompt for this drill:**

```text
Guide me through Part 7.4 on my own computer. Before restoring, verify the
PostgreSQL 14 tool paths, the new private socket directory and the data
location printed by SHOW data_directory. Never substitute an existing system
or classroom database. Explain each expected result. After restore, compare
the revision and seat count with my saved expectations and list the key
archive's filenames without printing their contents. Stop and clean up only
this drill's temporary instance and directory when the checks are finished.
Report what the drill proves and which recovery checks remain.
```

## 7.5 Make backups a habit

**What you're doing.** Deciding when to back up and which copies to keep.

**Why.** A backup only helps if it's recent.

**Steps.**

- Run [7.2](#72-back-up-the-database) on a regular schedule, following your
  school's or district's policy if it has one.
- Run [7.3](#73-back-up-the-keys-and-settings) after anything in `/etc/cth` changes.
- Choose a retention window that meets the classroom deletion rules and your
  approved local policy. A backup taken before a student, class or account
  deletion can contain the deleted records even if it is your newest backup.
  Retire affected archives, restore-drill copies and provider snapshots, then
  verify a replacement backup taken after the deletion. Do not restore an old
  copy to recreate deleted identities. If provider retention or school policy
  conflicts with this requirement, resolve that conflict before continuing.
  [Retention authority](../INVARIANT/ARCHITECTURE/INV-ARC-018_PII_STORAGE_AND_RETENTION_ENFORCEMENT.md#vii-prohibited-storage-patterns)
- Test a backup with [7.4](#74-test-that-a-backup-restores) after your first
  backup, and again whenever your policy calls for it.

**What you should see.** Your latest encrypted backup files, dated.

**If something looks wrong.** If you've missed a scheduled backup, run one now.

## 7.6 Renew the certificate

**What you're doing.** Getting a new certificate before the old one expires,
and putting it in place.

**Why.** When the certificate expires, Cloudflare refuses to connect to your
server and your site goes down. A manually issued Let's Encrypt certificate
doesn't renew itself.

**Steps.** About two weeks before the expiry date in your note, on the server
as root:

```bash
CTH_HOSTNAME=classroom.example.org
certbot certonly --manual --preferred-challenges dns -d "$CTH_HOSTNAME"
```

Choose to renew when asked, and create the new TXT record exactly as in
[Part 4, step 4.4](part-4-describe-your-installation.md#44-get-the-https-certificate).
Then:

```bash
install -m 0644 "/etc/letsencrypt/live/$CTH_HOSTNAME/fullchain.pem" /etc/cth/tls/origin.crt
install -m 0600 "/etc/letsencrypt/live/$CTH_HOSTNAME/privkey.pem" /etc/cth/tls/origin.key
systemctl restart cth-ingress.service
cd /root/cth-installer
python3 infra/self-hosting/install.py check ingress --config /etc/cth/installation.json
openssl x509 -in /etc/cth/tls/origin.crt -noout -enddate
```

Update the expiry date in your note, and back up `/etc/cth` again ([7.3](#73-back-up-the-keys-and-settings)).

> [!NOTE]
> The project hasn't rehearsed this renewal on a reference server yet. If the
> `check ingress` line doesn't end in `"result": "ok"`, see
> [Troubleshooting](troubleshooting.md).

**What you should see.** `"stage": "ingress"` … `"result": "ok"`, and a
`notAfter=` date later than the old expiry. Record that actual date and verify
the site from an external browser too. Manual certificates need an attended
renewal unless authentication hooks are configured; this tutorial does not
configure them. [Certbot manual renewal](https://eff-certbot.readthedocs.io/en/stable/using.html#manual)

**If something looks wrong.** If `cth-ingress` won't start, run
`journalctl -u cth-ingress.service -n 30 --no-pager`. The usual causes are
swapped certificate and key files or a wrong file mode.

## 7.7 Ubuntu updates and reboots

**What you're doing.** Keeping the operating system patched.

**Why.** Security fixes for Ubuntu, PostgreSQL, Redis and nginx come through
Ubuntu's updates.

**Steps.**

- Check your provider image's security-update configuration; do not assume
  automatic updates are enabled. On the server, inspect
  `systemctl list-timers --all apt-daily-upgrade.timer` and
  `apt-config dump | grep -E 'APT::Periodic::(Update-Package-Lists|Unattended-Upgrade)'`.
  If they are absent or disabled, follow your provider's Ubuntu update
  instructions or arrange help. The CTH installer does not configure this.
- Some updates need a reboot. If the file `/var/run/reboot-required` exists,
  back up ([7.2](#72-back-up-the-database)), then run `reboot` at a quiet time.
- After any reboot, log in and run `check readiness` as in
  [Part 6, step 6.7](part-6-first-use.md#67-check-health-from-the-server).

**What you should see.** `"result": "ok"` after the reboot. All CTH services
start on their own.

**If something looks wrong.** See [Troubleshooting](troubleshooting.md#host-or-postgres-check-fails-after-ubuntu-updates).

## 7.8 Upgrading CTH and rolling back

**What you're doing.** Planning how you'll move to a newer CTH release.

**Why.** New releases fix bugs and security problems.

The installer sets up one release on an empty server. It doesn't update an
existing installation by rerunning `apply`. An **upgrade** places a new CTH
version beside the old one and, when necessary, changes the database structure
through a **migration**. A **rollback** returns to a previous working version;
whether that's possible depends on what changed in the database.

Follow [Upgrade your CTH](upgrades.md) for the complete sequence: identify what
changed, rehearse it, take backups, switch the service, verify the result and
choose a recovery path if it fails. The walkthrough includes an agent prompt
for turning the release's changes into a plan for your particular server.

**Checkpoint:** before changing a working installation, you should know the
old and new version identifiers, the backup you can restore, whether there
are database changes and how you'll recover without losing newer records.
Keep the original installation manifest and journal intact. Their recorded
SHA identifies the first installation, not every future application version.

## 7.9 Reading logs

**What you're doing.** Finding out what a service is doing or why it failed.

**Why.** Logs are the first place to look when something's wrong.

**Steps.** On the server as root:

| To see | Run |
| --- | --- |
| Whether every CTH service is running | `systemctl status cth-web.service cth-ingress.service cth-rate-limit.service cth-student-setup.service --no-pager` |
| The web app's recent messages | `journalctl -u cth-web.service -n 50 --no-pager` |
| The app's own log file | `tail -n 50 /var/log/cth-web/app.log` |
| The HTTPS front end | `journalctl -u cth-ingress.service -n 50 --no-pager` |
| Messages since the last boot | add `-b` to a `journalctl` command |

`systemctl` asks Ubuntu's service manager what is running. `journalctl`
reads the messages those services recorded. `-u` chooses a service; `-n 50`
limits the output to the latest 50 entries; `--no-pager` prints and returns
to the prompt. If you omit it and land in a scrolling viewer, press **q** to
leave the viewer.

**What you should see.** `active (running)` for each service, and recent log
lines with timestamps. A line that says `ERROR` needs context: identify when
it occurred and which operation it belongs to before changing anything.

**If something looks wrong.** Logs can contain student names and other
private details. Read them on the server; if you share an excerpt to get
help, remove names, usernames, IP addresses and anything that looks like a key
first.

## 7.10 Optional: maintenance mode with Cloudflare Access

**What you're doing.** Closing the site to everyone but you, behind a
Cloudflare email-code sign-in, and opening it again afterwards.

**Why.** Access restricts new web requests to the people you admit. It does
not stop the scheduler, existing work or other server-side writers. For a
final backup or work requiring no writes, stop the application as described
in Part 8. The installer no longer requires an Access probe, but Access is
the designated maintenance gate in [DOM-OPS-001](../DOMAIN/DOM-OPS-001_OPERATIONS_DOMAIN.md#application-availability-gate);
do not add a second maintenance gate inside CTH.

**Steps to turn maintenance mode on** *(Cloudflare Zero Trust, November 2026;
the menus may move)*.

1. In the Cloudflare dashboard, open **Zero Trust**. The first time, choose a
   team name and the **Free** plan. Cloudflare may ask for a payment method
   even on the free plan.
2. Open **Access → Applications → Add an application** and choose
   **Self-hosted**.
3. Name it "CTH". For the domain, enter your CTH hostname with no path, so the
   whole site is covered.
4. Add a policy: **Action** Allow, **Include** Emails, and enter your own
   email address. Keep the sign-in method **One-time PIN**, and save.

**Steps to turn it off.** Delete the "CTH" application in **Access →
Applications**.

**What you should see.** While it's on, a private browser window opening any
page on your site lands on a Cloudflare page asking for an email address.
An unapproved identity must not gain access. Test both your admitted session
and an unadmitted session; receiving an email is not proof of authorization.
Once you delete the application, pages load
normally again.

**If something looks wrong.** If a page loads without asking for an email
while maintenance mode is on, check the application's domain is exactly your
CTH hostname, with no path.

**Next:** [Part 8: Shut it down](part-8-shut-down.md), for when you're finished.
