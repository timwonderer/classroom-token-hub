# Encrypted off-host database backups

**Not installed yet.** The design, the rules it keeps, restore and the failure-mode questions are in
[`docs/ops/DATABASE_BACKUP_PLAN.md`](../../docs/ops/DATABASE_BACKUP_PLAN.md). The procedure that governs it is
`SOP-DB-005`. This page is the operator's install and run sheet. The same tool runs in one of two places:
on the droplet with a B2 bucket as the off-host copy (below), or on the operator's computer (macOS or Linux) with an
encrypted external drive as the off-host copy ([Scheduled backups from the operator's computer](#scheduled-backups-from-the-operators-computer)),
which is the placement `SOP-DB-005` proposes.

| File | Purpose |
|---|---|
| `cth_db_backup.py` | `backup`, `check`, `status`, `restore`. Python 3, `psycopg2`, `pg_dump`/`pg_restore`, `age`, `rclone`. Imports no application code. |
| `cth-db-backup.service` / `.timer` | One recovery point nightly at 03:15 Pacific. |
| `cth-db-backup-check.service` / `.timer` | Every 15 minutes: replacement baseline after a protected destruction. |
| `env.example` | `/etc/cth-db-backup/env` |
| `rclone.conf.example` | `/etc/cth-db-backup/rclone.conf` (Backblaze B2) |
| `cth_backup_scheduled.py` | The operator's-computer placement (macOS, Linux): drive check, tunnel, verify container, then `backup`, `check`, `status` or `drill`, and the one-copy rule. |
| `macos/*.plist` | launchd jobs: nightly `backup` at 03:15; `check` hourly at :15 except 03:15. |
| `linux/*` | systemd user units: nightly `backup` at 03:15; `check` hourly at :15 except 03:15. |

## Install on the production host

Run as root. Replace every `CHANGE_ME` and `<live-db>`.

1. **Packages.** `pg_dump` and `pg_restore` must be the **same** major version as the server and the verify
   database (14 today). A newer `pg_dump` writes settings an older server rejects (17's `SET transaction_timeout`
   fails on 14), and verification then fails. The tool checks this before every backup and restore and refuses on a
   mismatch. Install the client package for the server's major, not the unversioned `postgresql-client`:

   ```bash
   apt-get install age rclone python3-psycopg2 postgresql-client-14
   pg_dump --version   # must report 14.x
   ```

2. **System user.**

   ```bash
   useradd --system --home-dir /var/lib/cth-db-backup --shell /usr/sbin/nologin cth-backup
   ```

3. **Database roles.** A read-only role for the dump, and a scratch database every dump is restored into and
   checked against. Neither is the application role.

   ```sql
   -- psql as postgres
   CREATE ROLE cth_backup_reader LOGIN PASSWORD 'CHANGE_ME' IN ROLE pg_read_all_data;
   ALTER ROLE cth_backup_reader SET default_transaction_read_only = on;
   CREATE ROLE cth_backup_verify LOGIN PASSWORD 'CHANGE_ME';
   CREATE DATABASE cth_backup_verify OWNER cth_backup_verify;
   \c cth_backup_verify
   ALTER SCHEMA public OWNER TO cth_backup_verify;
   ```

   Both connect over `localhost` with a password; check `pg_hba.conf` allows that.

4. **Key pair, on the owner's Mac, not the droplet.** Reusing the identity of the earlier pre-release dumps is fine.

   ```bash
   age-keygen -o cth-backup.agekey   # store the file in the password manager, then delete it
   age-keygen -y cth-backup.agekey   # the public key, "age1..."
   ```

   Put the public key (and a second recipient, if you keep one) in `/etc/cth-db-backup/recipients.txt`.

5. **Bucket.** In Backblaze B2: a private bucket, lifecycle "Keep only the last version", and an application key
   restricted to that bucket with list, read, write and delete. Copy the key into `rclone.conf`.

6. **Files.**

   ```bash
   install -d -m 0755 /opt/cth-db-backup
   install -m 0755 infra/db-backup/cth_db_backup.py /opt/cth-db-backup/
   install -d -m 0750 -g cth-backup /etc/cth-db-backup
   install -m 0640 -g cth-backup infra/db-backup/env.example /etc/cth-db-backup/env
   install -m 0640 -g cth-backup infra/db-backup/rclone.conf.example /etc/cth-db-backup/rclone.conf
   install -m 0640 -g cth-backup /dev/null /etc/cth-db-backup/recipients.txt
   # edit all three, then:
   install -m 0644 infra/db-backup/cth-db-backup*.service infra/db-backup/cth-db-backup*.timer /etc/systemd/system/
   systemctl daemon-reload
   ```

7. **First point, by hand.**

   ```bash
   systemctl start cth-db-backup.service
   journalctl -u cth-db-backup.service -n 30
   sudo -u cth-backup bash -c 'set -a; . /etc/cth-db-backup/env; python3 /opt/cth-db-backup/cth_db_backup.py status'
   ```

   Expect `"health": "CURRENT"`.

8. **Restore drill** with the owner's identity (plan §5.3). Do not enable the timers until it passes.

9. **Enable.**

   ```bash
   systemctl enable --now cth-db-backup.timer cth-db-backup-check.timer
   systemctl list-timers 'cth-db-backup*'
   ```

10. Record the date, the first stem, the drill result and the bucket listing in an ops record.

## Pre-release backup from the operator's Mac

Every tagged release takes one point before dispatch with [`prerelease.sh`](prerelease.sh); the ordered steps,
and where this fits among them, are `SOP-DEP-002` §VII.A. Same checks as the nightly job; nothing is uploaded.
Plan §6 explains why the application is stopped first.

```bash
bash infra/db-backup/prerelease.sh backup    # verify container, tunnel, stop the app, take + verify the point
bash infra/db-backup/prerelease.sh counts    # every table count in the point equals live production's
umask 077; pbpaste > ~/cth-backup/identity.txt   # owner: the age key, from the clipboard
bash infra/db-backup/prerelease.sh restore   # restore + no-resurrection check; deletes the identity, closes the tunnel,
                                             # and on PASS deletes every older pre-release point (SOP-DB-005 §VIII)
bash infra/db-backup/prerelease.sh evidence <sha>   # sign + upload proof of the above (infra/release-gate/)
bash infra/db-backup/prerelease.sh close-tunnel   # only if a run is abandoned before restore
```

`evidence` is what `release-v2.yml`'s SSH calls actually require to succeed — see
[`infra/release-gate/README.md`](../release-gate/README.md). Without it, every one of those calls
refuses, including the harmless transport check.

The three steps share one SSH tunnel to production, owned through the control socket `~/cth-backup/tunnel.sock`:
`backup` opens it, `counts` and `restore` reuse it (or reopen it), and `restore` closes it on exit. Until
2026-10-22 nothing closed it; the v2.2.4 tunnel was still listening six days later and blocked the next backup.

One-time setup on the Mac: `brew install age postgresql@14 colima docker`;
`python3 -m venv ~/cth-backup-venv && ~/cth-backup-venv/bin/pip install psycopg2-binary`; the owner's public key in
`~/cth-backup/recipients.txt`; and the dump role's connection URL, through the tunnel at `127.0.0.1:55433`, in
`~/cth-backup/source_url` (mode 600). The role is `cth_backup_reader` once step 3 above exists. Points land in
`~/cth-backup/prerelease-<UTC date>/`. Record in the release record: the stem, `taken_at`, the revision and
`artifact_sha256` from the manifest, and both results. Then dispatch the release.

## Scheduled backups from the operator's computer

The tool on a schedule on the operator's computer (macOS or Linux), writing to an encrypted external drive instead of
a bucket. Every check of the droplet design still runs: snapshot-consistent dump, encryption to the owner's public
keys, restore into a scratch database and a row count for every table, a re-hash of every point on the drive, and
the replacement baseline that deletes every older point once a seat, class or user is destroyed. Retention is one
copy of one point (`SOP-DB-005` §VIII): the newest verified point, scheduled (kept on the drive only) or pre-release
(on the computer only). Each verified point deletes every older one, from either source. The droplet holds nothing.

[`cth_backup_scheduled.py`](cth_backup_scheduled.py) runs it and does nothing (and says so in the log) when:

- the drive is not mounted. The nightly run also posts a desktop notification;
- `classroom-economy` is not active on the droplet: a release (`prerelease.sh` stops it, the release restarts it) or
  an outage. A backup then could hold the locks a migration needs (plan §8 F10);
- another run holds `~/cth-backup/scheduled/wrapper.lock`. A `check` just exits; a `backup` waits up to 30 minutes.

It uses its own tunnel port (55435), verify container (`cth-sched-verify`, port 55436, data on tmpfs, removed after
every run) and state directory, so it never touches what `prerelease.sh` owns. It holds off system sleep while it
runs (`caffeinate` on macOS, `systemd-inhibit` on Linux), and posts a desktop notification on any failure where the
platform has one (`osascript`, `notify-send`).

| Platform | Scheduler | Drive mounts at | Logs |
|---|---|---|---|
| macOS | launchd, [`macos/`](macos/) | `/Volumes/CTH-Backup` | `~/Library/Logs/cth-db-backup/` |
| Linux | systemd user units, [`linux/`](linux/) | `/media/$USER/CTH-Backup` | `journalctl --user -u 'cth-backup-scheduled*'` |

Windows is not supported natively: `cth_db_backup.py` locks with `fcntl`. Under WSL2 the Linux steps apply, with
the drive's WSL mount point (for example `/mnt/e`) in `CTH_BACKUP_DRIVE`; that path is untested.

Settings are environment variables, or `KEY=VALUE` lines in `~/cth-backup/scheduled/env`: `CTH_BACKUP_DRIVE`,
`CTH_BACKUP_PG_BIN` (directory of the PostgreSQL 14 client tools, if not on `PATH`), `CTH_BACKUP_SSH_HOST`
(default `root@cth`), `CTH_BACKUP_TUNNEL_PORT`, `CTH_BACKUP_VERIFY_PORT`.

### Install

1. **Tools.** Python 3.9+ with a venv holding `psycopg2-binary` at `~/cth-backup-venv` (as for the pre-release
   setup), `ssh`, a Docker engine, the PostgreSQL **14** client tools, `age`, `age-plugin-yubikey` and `rclone`.
   rclone treats the drive as a plain directory; no `rclone.conf` is needed. The plugin is needed to encrypt to a
   YubiKey, not only to decrypt with one.

   - macOS: `brew install age age-plugin-yubikey rclone postgresql@14 colima docker`, and in
     `~/cth-backup/scheduled/env`: `CTH_BACKUP_PG_BIN=/opt/homebrew/opt/postgresql@14/bin`.
   - Debian or Ubuntu: `apt-get install age rclone docker.io postgresql-client-14` (from the PostgreSQL apt
     repository if the distribution lacks 14) and `age-plugin-yubikey` from its release page;
     `CTH_BACKUP_PG_BIN=/usr/lib/postgresql/14/bin`. Add yourself to the `docker` group.

   **YubiKey recipients** (`SOP-DB-005` D6). For each of the two YubiKeys: `age-plugin-yubikey` (follow its prompts;
   it creates the key on the YubiKey and prints an `age1yubikey1…` recipient), then append that recipient to
   `~/cth-backup/recipients.txt`, which then holds three lines: the owner's key and the two YubiKeys. Every point,
   pre-release ones included, is then readable with any one of the three. Keep one YubiKey away from the computer.

2. **Read-only role on the droplet.** Only the first statement of step 3 above: `cth_backup_reader` with
   `pg_read_all_data` and `default_transaction_read_only`. The scratch database runs on the computer, so skip
   `cth_backup_verify`. Do not reuse the pre-release URL: it names the application role, which can write.

3. **Drive.** Name the volume `CTH-Backup` and encrypt it: APFS (Encrypted) in Disk Utility on macOS, LUKS on Linux
   (`gnome-disks`, "Encrypt with LUKS + ext4"). Let it unlock unattended (`SOP-DB-005` D3): on macOS
   tick "Remember this password in my keychain" when first mounting it; on Linux add a key file to the LUKS volume
   and list it in `/etc/crypttab`. The points are already encrypted to the owner's keys, so the
   volume's own encryption protects only file names, dates and sizes. No age identity is ever stored on it.

4. **Keep the points out of other backups.** A copy of a point in another backup outlives the purge that deletes it.
   On macOS, even with no Time Machine destination today (`tmutil destinationinfo`):

   ```bash
   tmutil addexclusion ~/cth-backup
   sudo tmutil addexclusion -v /Volumes/CTH-Backup
   ```

   On Linux, exclude `~/cth-backup` and the drive from whatever backs up the home directory (Déjà Dup, Timeshift).

5. **Files.** Copied out of the checkout, so switching branches never changes what runs. Repeat after any change to
   either script.

   ```bash
   mkdir -p -m 0700 ~/cth-backup/scheduled/bin
   cp infra/db-backup/cth_db_backup.py infra/db-backup/cth_backup_scheduled.py ~/cth-backup/scheduled/bin/
   (umask 077; printf '%s\n' 'postgresql://cth_backup_reader:CHANGE_ME@127.0.0.1:55435/classroom_economy' \
     > ~/cth-backup/scheduled/source_url)
   ```

   `~/cth-backup/recipients.txt` is shared with the pre-release setup. `ssh root@cth` (or `CTH_BACKUP_SSH_HOST`) must
   work without a prompt: the job runs with `BatchMode=yes` and fails rather than waiting.

6. **First point, by hand.** On macOS, allow access to the removable volume if asked.

   ```bash
   ~/cth-backup-venv/bin/python ~/cth-backup/scheduled/bin/cth_backup_scheduled.py backup
   ~/cth-backup-venv/bin/python ~/cth-backup/scheduled/bin/cth_backup_scheduled.py status   # "health": "CURRENT"
   ```

7. **Restore drill** with the owner's identity. Do not enable the schedule until it passes. Put the identity in
   `~/cth-backup/identity.txt` (mode 600; on macOS `umask 077; pbpaste > ~/cth-backup/identity.txt`), then:

   ```bash
   ~/cth-backup-venv/bin/python ~/cth-backup/scheduled/bin/cth_backup_scheduled.py drill   # deletes the identity
   ```

   Then once per YubiKey, with it plugged in: `age-plugin-yubikey --identity > ~/cth-backup/identity.txt` (a stub
   naming the key on the YubiKey, not the key itself) and the same `drill`. It asks for the PIN and a touch.

8. **Enable the schedule and the wake.** The computer wakes five minutes before the nightly run and the runner keeps
   it awake until the run ends.

   macOS (`pmset` holds one repeating schedule, so this replaces any other):

   ```bash
   mkdir -p ~/Library/Logs/cth-db-backup ~/Library/LaunchAgents
   for job in db-backup db-backup-check; do
     sed "s#__HOME__#$HOME#g" infra/db-backup/macos/com.classroomtokenhub.$job.plist \
       > ~/Library/LaunchAgents/com.classroomtokenhub.$job.plist
     launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.classroomtokenhub.$job.plist
   done
   sudo pmset repeat wakeorpoweron MTWRFSU 03:10:00
   ```

   Linux (`linger` runs the timers while you are logged out; the wake needs root, as user timers cannot wake the
   system):

   ```bash
   mkdir -p ~/.config/systemd/user && cp infra/db-backup/linux/cth-backup-scheduled* ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now cth-backup-scheduled.timer cth-backup-scheduled-check.timer
   sudo loginctl enable-linger "$USER"
   sudo rtcwake -m no -t "$(date -d 'tomorrow 03:10' +%s)"   # one wake; repeat it from a root cron job nightly
   ```

9. Record the date, the first stem, the drill result and the drive listing in an ops record.

To stop: `launchctl bootout gui/$(id -u)/com.classroomtokenhub.db-backup` (and `-check`), or
`systemctl --user disable --now cth-backup-scheduled.timer cth-backup-scheduled-check.timer`.

### Running it

- **Monthly drill:** step 7 again; record it in `docs/ops/audits/RESTORE_DRILL_<date>.md` (plan §5.3).
- **Disaster recovery or rollback:** plan §5.2, taking the one point there is: on the drive's
  `cth-db-backups/production/`, or, after a release until the next nightly point, in
  `~/cth-backup/prerelease-<UTC date>/points/` (the newest folder with a `restore.ok`).
- **Moving to another computer:** steps 1, 3 (only the unlock), 4, 5, 6 and 8 there, with the same drive and keys.
  The state directory need not move: with none, the first run is a baseline and deletes the older point once its
  own is verified.
- **The computer must be running** for a run. One woken for the nightly run backs up on time; a destruction that
  happens while it is off or the drive is detached is purged at the next `check` after both are back.
