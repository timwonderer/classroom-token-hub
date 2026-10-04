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

1. **Packages.** `pg_dump` must be at least the server's major version (14 today).

   ```bash
   apt-get install age rclone python3-psycopg2 postgresql-client
   pg_dump --version
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

For a release before the timers run, such as v2.1.1. Same checks as the nightly job; nothing is uploaded. Plan §6
explains why the application is stopped first.

```bash
# once: tools
brew install age libpq          # libpq provides pg_dump / pg_restore; add its bin to PATH
python3 -m venv ~/cth-backup-venv && ~/cth-backup-venv/bin/pip install psycopg2-binary

# throwaway Postgres whose data lives in memory, so restored plaintext never reaches the disk
docker run --rm -d --name cth-verify -e POSTGRES_PASSWORD=verify \
  -p 127.0.0.1:55432:5432 --tmpfs /var/lib/postgresql/data postgres:14
docker exec cth-verify createdb -U postgres cth_backup_verify
docker exec cth-verify createdb -U postgres cth_restore_check

# tunnel to production Postgres
ssh -N -L 55433:127.0.0.1:5432 root@<prod-tailscale-host> &

# stop the application and confirm it is inactive
ssh root@<prod-tailscale-host> 'systemctl stop classroom-economy; systemctl is-active classroom-economy'

export CTH_BACKUP_SOURCE_URL='postgresql://<role>:<password>@127.0.0.1:55433/<live-db>'
export CTH_BACKUP_VERIFY_URL='postgresql://postgres:verify@127.0.0.1:55432/cth_backup_verify'
export CTH_BACKUP_AGE_RECIPIENTS_FILE=~/cth-backup/recipients.txt
export CTH_BACKUP_STATE_DIR=~/cth-backup/prerelease
unset CTH_BACKUP_REMOTE

# 1. take and verify the point
~/cth-backup-venv/bin/python infra/db-backup/cth_db_backup.py backup --reason manual

# 2. prove the owner's identity decrypts it and it restores whole
P=$(ls -t ~/cth-backup/prerelease/points/*.dump.age | head -1)
~/cth-backup-venv/bin/python infra/db-backup/cth_db_backup.py restore \
  --artifact "$P" --manifest "${P%.dump.age}.manifest.json" --identity <path-to-identity> \
  --target-url 'postgresql://postgres:verify@127.0.0.1:55432/cth_restore_check' \
  --live-url "$CTH_BACKUP_SOURCE_URL"

# 3. discard the in-memory database
docker stop cth-verify
```

`<role>` is `cth_backup_reader` once step 3 above exists; until then, the role used for the 2026-10-02 dump. Remove
the identity file as soon as step 2 finishes. Record in the release record: the stem, `taken_at`, the revision and
`artifact_sha256` from the manifest, and both results. Then dispatch the release.
