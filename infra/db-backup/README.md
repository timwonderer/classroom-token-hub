# Encrypted off-host database backups

**Proposal, not installed.** The design, the rules it keeps, restore and the failure-mode questions are in
[`docs/ops/DATABASE_BACKUP_PLAN.md`](../../docs/ops/DATABASE_BACKUP_PLAN.md). This page is the operator's install
and run sheet.

| File | Purpose |
|---|---|
| `cth_db_backup.py` | `backup`, `check`, `status`, `restore`. Python 3, `psycopg2`, `pg_dump`/`pg_restore`, `age`, `rclone`. Imports no application code. |
| `cth-db-backup.service` / `.timer` | One recovery point nightly at 03:15 Pacific. |
| `cth-db-backup-check.service` / `.timer` | Every 15 minutes: replacement baseline after a protected destruction. |
| `env.example` | `/etc/cth-db-backup/env` |
| `rclone.conf.example` | `/etc/cth-db-backup/rclone.conf` (Backblaze B2) |

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
bash infra/db-backup/prerelease.sh restore   # restore + no-resurrection check; deletes the identity, closes the tunnel
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
