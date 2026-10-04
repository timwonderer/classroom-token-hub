# Production database backup and restore plan

**Status: proposal, not applied.** Nothing here has been installed on the production host. This is the
implementation candidate for the "No database backup of any kind exists" item in
[POST_LAUNCH_TRACKER_2026.md](../TRACKING/POST_LAUNCH_TRACKER_2026.md) §IV-B. That item says a failure-mode
review of the owner's backup model comes before any normative text or implementation. This document is input to
that review (see §8): it is descriptive, not normative, and it settles nothing the review has not.

Tooling: [`infra/db-backup/`](../../infra/db-backup/README.md).

---

## 1. Where things stand (2026-10-04)

- DigitalOcean droplet backups are off. There is no scheduled dump and no WAL archiving.
- The only recovery points are manual, `age`-encrypted pre-release dumps taken from the operator's Mac
  ([DEPLOY_2026-09-30_314158d53.md](audits/DEPLOY_2026-09-30_314158d53.md),
  [DEPLOY_2026-10-02_5ac05ea6f.md](audits/DEPLOY_2026-10-02_5ac05ea6f.md)). The newest is 2026-10-02 04:44:28Z.
- `scripts/backup-database.sh` and `scripts/restore-database.sh` were v1-era and never scheduled. They wrote
  plaintext gzip dumps to the droplet's own disk and restored over the live database with a stale service name. This
  change removes them.

## 2. Rules the design has to keep

| Source | Rule |
|---|---|
| INV-CORE-000 §III.5 | Backup and restoration must not be used to restore accounts. |
| INV-ARC-018 §VII.4 | PII must not survive in backups beyond the retention window of the owning record; backup retention aligns with class lifecycle deletion. |
| SOP-SEC-001 §V.3, §VII | Backups carry the same access controls and deletion policy as the source; never used to restore deleted accounts or class-scoped identity data. |
| SPEC-IDEN-001, INV-ARC-018 §IX | The student-setup Redis store must never be captured by a backup. This plan only dumps Postgres. |
| SOP-DEP-002 §VI.2, §IX | A release needs a current backup and tested restore instructions; rollback of an irreversible migration is restore-from-backup, not `alembic downgrade`. |
| Owner direction, 2026-09-30 | Scheduled encrypted off-host backups. Seat, class or teacher-account deletion is a protected destruction. Once one completes, older recovery points are unacceptable, but are superseded only after a new verified baseline exists. Health is CURRENT or STALE/DEGRADED. |

## 3. Design

### 3.1 One recovery point

Each run of `cth_db_backup.py backup`:

1. Opens a read-only `REPEATABLE READ` transaction and exports its snapshot (`pg_export_snapshot`), the method used
   for both pre-release dumps. Inside that snapshot it records every public table's row count, the Alembic revision,
   and the ids of every seat, class and user.
2. Runs `pg_dump --format=custom --snapshot=…` on that snapshot, leaving out the row data of
   `teacher_signup_attempts` (30-minute staging rows; same exclusion as both earlier dumps).
3. Sends the identical byte stream to two places at once: `age` (encrypting to the owner's **public** key, written
   to disk) and `pg_restore` into an empty scratch database on the same cluster. No plaintext file is written.
4. Compares the scratch database with the snapshot: same tables, same row count in every table, same Alembic
   revision. Any mismatch fails the run and the artifact is discarded. The scratch database is emptied whether the
   run passes or fails, and again at the start of the next run.
5. Uploads the encrypted artifact off-host, downloads it back and checks its SHA-256, then uploads the manifest.
   A point counts as complete off-host only when its manifest is there.
6. Applies retention (§3.4) and re-hashes every retained off-host point against its manifest.

The host holds only the `age` recipient. It can make recovery points but cannot read any of them. The identity
(private key) lives in the owner's password manager.

Verification proves the plaintext restores completely and that the ciphertext off-host is byte-identical to what was
written. It does not prove the owner's identity decrypts it: that is the restore drill (§5.3).

### 3.2 Schedule

| Timer | When | What |
|---|---|---|
| `cth-db-backup.timer` | 03:15 America/Los_Angeles nightly, up to 10 min jitter | One scheduled point |
| `cth-db-backup-check.timer` | Every 15 minutes | Detects a protected destruction and takes a replacement baseline (§3.3) |

At today's size (46 tables, about 9,400 rows, an 800 KB dump) a run takes a few seconds.

### 3.3 Replacement baseline after a protected destruction

A protected destruction is detected, not reported by the application: **a seat, class or user id present in the
newest verified point is missing from the database now**. This catches every deletion path the same way
(teacher-initiated, class destruction, the 180-day and 30-day account retention jobs) with no application change.
Ids are never reused (serial integers and UUIDs), so a missing id always means a deletion.

When the check, or the nightly run, sees one:

1. It takes a new point marked `baseline` and verifies it exactly as in §3.1, including the off-host re-hash.
2. Only then does it delete every older point, off-host first and then on the host.
3. If the baseline fails, the older points are kept (the owner's "superseded only after a new verified baseline
   exists") and health is STALE until a baseline succeeds. Every 15-minute check retries.

`baseline_at` is persisted, so an interrupted purge is finished by the next 15-minute check, not left for the next
nightly run. The check holds the same lock as the nightly run for its whole duration, so the two never overlap.

### 3.4 Retention

- Off-host: the newest 14 points (`CTH_BACKUP_KEEP_REMOTE`), about two weeks of nightly points.
- On the host: the newest 2 (`CTH_BACKUP_KEEP_LOCAL`), encrypted, for a fast restore.
- In both places, nothing older than the newest replacement baseline, whatever the counts say.

### 3.5 Health

`cth_db_backup.py status` prints JSON and exits 0, 1 or 2.

| Health | Meaning |
|---|---|
| CURRENT (0) | Newest verified point is under 26 hours old, is off-host, and no destruction has happened since it. |
| STALE (1) | No point, the newest point is over 26 hours old, or a destruction has happened since the newest point and the replacement baseline has not completed. |
| DEGRADED (2) | The last run failed, the newest point has no off-host copy, or points older than the baseline are still held (purge incomplete). |

An off-host point that no longer matches its manifest fails every run until retention removes it or the operator
deletes it, so health stays DEGRADED rather than going quiet.

### 3.6 Off-host storage

**Recommended: Backblaze B2**, a different provider from the droplet, so one account problem cannot take both. At
today's size two weeks of points is under 15 MB, inside B2's free 10 GB. Use the native `b2` rclone backend with
`hard_delete = true` and a bucket lifecycle of "keep only the last version": B2 otherwise keeps every version of a
file, and a "deleted" pre-destruction point would survive as a hidden version. DigitalOcean Spaces also works
(no versioning by default) but shares the droplet's provider.

The application key is restricted to the one bucket. It needs list, read, write and **delete**: the baseline rule
cannot work without delete. See §8, F1.

### 3.7 What the backup does not contain

- **Application secrets.** `ENCRYPTION_KEY` (every name column and TOTP secret), `PEPPER_KEY` (every username
  lookup), `AUDIT_HMAC_KEY` and `SECRET_KEY` are not in the database. A restore without the same `ENCRYPTION_KEY`
  and `PEPPER_KEY` yields a database nobody can sign in to and whose names cannot be read. They must be stored off
  the droplet, separately from the bucket. The tracker's §IV-B "leftover v1 data" item is still waiting on the owner
  confirming this.
- The student-setup Redis store, by rule.
- `teacher_signup_attempts` row data.

## 4. Installing (operator, when approved)

Step by step in [`infra/db-backup/README.md`](../../infra/db-backup/README.md): two database roles, a system user,
the `age` key pair, the B2 bucket and key, the config files, the units, then one manual run, a restore drill and
enabling the timers.

## 5. Restore

### 5.1 Ground rules

- Restore is for whole-database disaster recovery and release rollback only. There is no per-table, per-class or
  per-account restore, and the tool offers none (INV-CORE-000 §III.5).
- Always restore into a **new, empty** database. The tool refuses a target that has any table. It never touches
  the live database and never cuts over; the operator does that.
- Use the newest point unless the reason for restoring is in it (for example, a bad migration ran before it).

### 5.2 Disaster recovery or rollback

1. Stop the application: `systemctl stop classroom-economy`, and confirm it is `inactive`.
2. Fetch the point and its manifest (`rclone copy cth-offsite:cth-db-backups/production/<stem>.dump.age .` and the
   `.manifest.json`), or use the copy under `/var/lib/cth-db-backup/points/`.
3. Put the owner identity on the machine doing the restore for as short a time as possible (mode 600, removed
   afterwards). Doing the restore from the operator's Mac through an SSH tunnel keeps it off the droplet entirely.
4. Create an empty database owned by the application role, for example `classroom_economy_restored`.
5. Run, as the application role:

   ```bash
   python3 cth_db_backup.py restore \
     --artifact <stem>.dump.age --manifest <stem>.manifest.json --identity owner.agekey \
     --target-url postgresql://<app-role>@localhost/classroom_economy_restored \
     --live-url  postgresql://cth_backup_reader@localhost/<live-db>
   ```

   It checks the SHA-256 against the manifest, decrypts, restores, compares every table count and the revision, and,
   refuses if the restored data holds any seat, class or user that the live database has since destroyed. Without
   `--live-url` it refuses to run. When the live database no longer exists, `--live-database-lost` lets it restore
   without that check and marks the result UNVERIFIED. Nothing then available, including `status` and the bucket
   listing, can prove that no destruction followed the point: a deletion in the last minutes before the loss may not
   have reached a baseline. Cutting over in that case is the owner's decision (F6).
6. Cut over: `ALTER DATABASE <live-db> RENAME TO <live-db>_replaced_<date>;` then
   `ALTER DATABASE classroom_economy_restored RENAME TO <live-db>;`
7. Start the application, check `/health` on `127.0.0.1:8000`, and run the SOP-DEP-002 smoke checks.
8. Drop `<live-db>_replaced_<date>` once the restore is confirmed. It may hold data the restore removed on purpose.
9. Write an incident or release record with the stem, the manifest's revision and counts, and every result above.

### 5.3 Restore drill

Monthly, and after any change to this tooling or the key: fetch the newest point, restore it with the owner's
identity into a throwaway Postgres (on the Mac, a container with its data directory on `tmpfs`), and record the
result in `docs/ops/audits/RESTORE_DRILL_<date>.md`. This is the only check that the owner's identity decrypts
the points.

## 6. One-off pre-release backup (for v2.1.1 and any release before the timers run)

v2.1.1 carries migrations that cannot be downgraded, so a verified backup is its only rollback. Until the timers are
installed, take the point from the operator's Mac with the same tool, local-only. The full commands are in
[`infra/db-backup/README.md`](../../infra/db-backup/README.md#pre-release-backup-from-the-operators-mac).

1. **Stop the application first.** The snapshot is then the exact state the migrations start from, and no student
   write can land between the backup and the release and be lost by a rollback.
2. Take the point with `backup --reason manual` and `CTH_BACKUP_REMOTE` unset. It restores into a throwaway local
   Postgres and checks every table count, as the scheduled job does.
3. Run `restore` with the owner's identity into a second empty database, with `--live-url`. This proves the key
   decrypts it.
4. Record the stem, `taken_at`, revision, artifact SHA-256 and both results in the release record, then dispatch the
   release.

Health will read DEGRADED ("no off-host copy"). That is expected for a local-only point; store it as the earlier
pre-release dumps were stored.

## 7. Decisions for the owner

1. Off-host provider: B2 (recommended) or DigitalOcean Spaces.
2. Retention: 14 off-host points. Shorter shrinks the window in F6; longer gives more history.
3. Alerting: today a failed run is a failed systemd unit and journal lines (which reach Loki). Something has to
   page the owner on STALE or DEGRADED (F5).
4. A second `age` recipient (for example a key printed and stored offline), so losing one key does not lose every
   backup (F7).
5. Whether to stop the application before every pre-release backup (§6 recommends yes).

## 8. Failure modes, for the owner's review

| # | Failure | What happens under this design | Open question |
|---|---|---|---|
| F1 | Droplet root compromise | Attacker reads the env file: database passwords, bucket key, `age` recipient. Cannot decrypt any point. **Can delete every off-host point**, because the baseline rule needs delete. | Accept, or move the purge to a credential held off the droplet (the host then writes only, and an off-host job deletes)? That makes the purge depend on a second machine. |
| F2 | Baseline fails after a destruction | Older points kept, health STALE, retried every 15 minutes. Meanwhile pre-destruction PII exists in backups, which INV-ARC-018 §VII.4 forbids beyond the record's retention. | The owner's "superseded only after a verified baseline" was chosen over deleting first. Confirm, and set how long STALE may last before someone acts. |
| F3 | Destruction to purge window | Up to 15 minutes plus a run. | Acceptable? The application could trigger the check directly after a destruction instead. |
| F4 | Deletions that are not seat, class or user | Not detected. Rows removed by other retention (expired recovery codes, for example), and identity data cleared in place while the seat row survives (claim-name hashes, roster fingerprint), stay in points up to 14 days. | Is 14 days within each such record's retention window, or should some of these also count as protected destructions? |
| F5 | Silent failure | Nothing pages anyone today. | See §7.3. |
| F6 | Restoring a pre-destruction point | Purged after a baseline. Before the purge, and only then, such a point exists; `restore --live-url` refuses it while the live database exists. With the live database gone, nothing can establish that the newest point is safe, and the tool restores only with `--live-database-lost`, marked UNVERIFIED. | Accept that risk for a total loss, or refuse to cut over without some durable record of destructions kept outside the database? |
| F7 | Owner identity lost | Every point is unreadable. | Second recipient (§7.4). |
| F8 | Application secrets lost | Restored database is unusable (names unreadable, no sign-in). | Confirm `ENCRYPTION_KEY`, `PEPPER_KEY`, `AUDIT_HMAC_KEY` are stored off the droplet. |
| F9 | Plaintext in the scratch database | Exists for seconds per run, on the same cluster as the source. A crash leaves it until the next 15-minute check empties it. | Acceptable on the source host? |
| F10 | Backup overlaps a release migration | `pg_dump` holds ACCESS SHARE locks; a migration needing ACCESS EXCLUSIVE waits, and the 10 s `lock_timeout` on the application role fails it. | Don't release during 03:15–03:30 Pacific. Runs take seconds today. |
| F11 | Postgres upgraded past the client | `pg_dump` refuses an older client; the run fails loudly (DEGRADED). | Upgrade `postgresql-client` with the server. |
| F12 | B2 keeps "deleted" files | `hard_delete = true` and a keep-last-version lifecycle. | Verify with `rclone ls --b2-versions` after the first baseline. |
| F13 | No point in time between nightly points | Up to a day of writes lost on restore. | WAL archiving would close this, but its archive also has to obey the baseline rule, which is harder. Out of scope here. |

## 9. Evidence

Tested 2026-10-04 in a development container (PostgreSQL 16, `age` 1.1, rclone 1.60 with a local directory as the
off-host target) against a database built by the real migration chain to `f9a3c7d1e620` (45 tables, 23 triggers),
seeded with 2 classes, 30 users and 30 seats. Not run against production.

| Check | Result |
|---|---|
| Scheduled point | Restored into scratch, all 45 table counts and the revision matched; `teacher_signup_attempts` restored empty; off-host copy re-hashed. Health CURRENT. |
| Restore drill with the owner identity into an empty database | Matched its manifest; 23 triggers restored. |
| Restore into a non-empty database | Refused. |
| Retention, 4 points with keep 3 | Oldest deleted off-host; host kept 2. |
| Seat and user deleted, then `status` | STALE, naming 1 seat and 1 user. |
| `check` after that deletion | Baseline taken and verified, then all 3 older points deleted off-host and on the host. Health CURRENT. |
| Restore of a pre-destruction point with `--live-url` | Restored, then REFUSE CUTOVER naming 1 seat and 1 user. |
| Restore with neither `--live-url` nor `--live-database-lost` | Refused before restoring. |
| Seat deleted, then the nightly run | That run became the baseline and purged the older points. |
| Off-host artifact altered | Next run failed its re-hash; health DEGRADED. |
| `age` given a bad recipient | Run failed; no artifact left; scratch database empty. |
| Local-only run (`CTH_BACKUP_REMOTE` unset) | Verified point on disk; health DEGRADED, "no off-host copy". |
| `check` while a backup holds the lock | Exits 0 without running. |
| `check` with a table left in the scratch database | Emptied it. |
| Baseline taken, then the purge failed | DEGRADED, older points listed; the next 15-minute `check` finished the purge. Health CURRENT. |
| Manifest upload failed after the artifact uploaded | The off-host artifact was removed; no incomplete point left. |
| Artifact without a manifest found off-host | Removed by the next run before retention was counted. |
| State file lost while points exist | Next run treated itself as a baseline and deleted every older point once verified. |
