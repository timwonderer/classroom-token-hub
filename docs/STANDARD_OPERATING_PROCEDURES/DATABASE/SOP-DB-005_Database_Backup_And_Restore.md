# SOP-DB-005: Database Backup and Restore

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DB-005       | 1.0     | 2026-11-25     | —          | Normative (SOP Tier 2) |

> [!IMPORTANT]
> **Not yet installed.** Until the install record of §XII exists, the only recovery points are the pre-release
> points of `SOP-DEP-002` §VII.A.

## I. Purpose

Keep scheduled, encrypted, verified recovery points of the production database, kept off the droplet, without
letting a backup outlive a deletion the application has carried out. Restore whole-database for disaster recovery
and release rollback only.

## II. Scope

The production PostgreSQL database. Out of scope, and never captured:

- the student-setup memory store (SPEC-IDEN-001; INV-ARC-018 §IX);
- application secrets (`ENCRYPTION_KEY`, `PEPPER_KEY`, `AUDIT_HMAC_KEY`, `SECRET_KEY`), which are kept separately
  (§XI, D7);
- the row data of `teacher_signup_attempts` (30-minute staging rows; schema kept);
- the status site's Firestore.

## III. Authority Level

Normative (SOP Tier 2). Subordinate to INV-CORE-000, INV-ARC-018 and SOP-SEC-001. `SOP-DEP-002` §VI.2 and
§VII.A and `SOP-DB-004` §IX rely on the recovery points this document defines.

## IV. Dependencies

- `infra/db-backup/cth_db_backup.py`: takes, verifies, retains, purges and restores points.
- `infra/db-backup/cth_backup_scheduled.py`, with `infra/db-backup/macos/` (launchd) or `infra/db-backup/linux/`
  (systemd user units): the schedule (§VII).
- `infra/db-backup/README.md`: install, drill and operation commands.
- `docs/ops/DATABASE_BACKUP_PLAN.md`: design and failure modes (descriptive).

## V. Rules every backup keeps

1. **No resurrection.** A backup is never used to restore an account, a class or any class-scoped identity data
   (INV-CORE-000 §III.5; SOP-SEC-001 §V.3, §VII). There is no per-account, per-class or per-table restore.
2. **Deletion reaches backups.** Once a seat, class or user is destroyed, every point taken before the destruction
   is deleted, wherever it is kept, as soon as a newer point has been verified (INV-ARC-018 §VII.4, §VIII).
3. **Only ciphertext at rest.** A point is encrypted to the owner's public key as it is written. No unencrypted dump
   is written to any disk. The machine that takes points holds only the public key.
4. **Same access as the source.** Points, the drive and the state directory carry the access controls of the
   production database (SOP-SEC-001 §V.3) and are excluded from every other backup (Time Machine, cloud sync).
5. **Verified or it does not count.** A point counts only after it has been restored into a scratch database whose
   tables, row counts and Alembic revision match those read inside the dump's own snapshot, and after its copy on the
   drive re-hashes to its manifest.

## VI. Recovery points

A point is one `age`-encrypted `pg_dump --format=custom` and its manifest (stem, `taken_at`, revision, table counts,
identity counts, SHA-256). Reasons: `scheduled`, `baseline` (taken after a destruction), `manual` (pre-release).

## VII. Placement and schedule

1. **Where.** The tool runs on the operator's computer, macOS or Linux, under the platform's scheduler (launchd or
   systemd), and reaches production through an SSH tunnel as the read-only role `cth_backup_reader`, never the
   application role. The off-host copy is an encrypted external drive (APFS Encrypted or LUKS). Moving to another
   computer needs only the drive, the keys and a reinstall. The droplet holds no points and no backup credential. (Placement is decision D1.)
2. **When.**
   - `backup`: nightly at 03:15 local. The computer wakes itself at 03:10 (`pmset` on macOS, `rtcwake` on Linux) and
     stays awake until the run ends; a run still missed (computer off) runs once at the next start.
   - `check`: every 15 minutes (on macOS also at login and whenever a volume mounts). It detects a destruction and takes the
     replacement baseline (§VIII.2).
3. **When not.** No run while the drive is absent, while `classroom-economy` is not active (a release or an
   outage), or while another run is in progress.

## VIII. Retention and the replacement baseline

1. **One copy.** Exactly one copy of one point exists: the newest verified one, whatever took it (owner ruling
   2026-11-25). A scheduled point is verified once it restored completely and its copy on the drive re-hashes to its
   manifest; it then lives only on the drive. A pre-release point is verified once its `restore` passed; it lives only
   on the computer. Each verified point deletes every older one, scheduled or pre-release, wherever it is. A point that
   fails verification deletes nothing.
2. **Baseline.** A destruction is detected as any seat, class or user id in the newest verified point that is
   missing from production. The next run takes a `baseline` point, verifies it in full, then deletes every older
   point on the drive and on the computer. If the baseline fails, older points are kept and health is STALE until one
   succeeds.
3. **Pre-release points.** A `SOP-DEP-002` pre-release point deletes every older pre-release point once `restore`
   passes. The scheduled job's next run (within 15 minutes of the application restarting) deletes the older point on
   the drive, and the next verified scheduled point deletes the pre-release one. A release can therefore be rolled back by restore only
   until that next scheduled point, which is after its health was verified (`SOP-DB-004` §IX); later, recovery is
   fix-forward.
4. **Consequence.** There is never an older point to fall back to. Damage that is already in the newest point when
   it is found (bad data written before the last backup) cannot be undone by restore.

## IX. Health and response

`cth_backup_scheduled.py status` reports:

| Health | Meaning | Operator response |
|---|---|---|
| CURRENT | Newest verified point is under 26 hours old, is on the drive, and no destruction has happened since. | None. |
| STALE | No point, the newest is over 26 hours old, or a destruction has no verified baseline yet. | When noticed: attach and unlock the drive, wake the computer, run `check`. No deadline (D4). |
| DEGRADED | The last run failed, the newest point is not on the drive, or points older than the baseline remain. | Read the log; fix and rerun `check`. |

Every failed run posts a desktop notification where the platform has one (D10).

## X. Restore

1. Whole database only, into a new empty database, never over the live one. The tool refuses a target that has any
   table, and refuses a point holding a seat, class or user that production has since destroyed.
2. Procedure: `docs/ops/DATABASE_BACKUP_PLAN.md` §5.2. Cut-over is the operator's act, with named approval as
   `SOP-DEP-002` §IX requires for a rollback.
3. With the live database lost, the cause decides (owner ruling 2026-11-25, D9). After an infrastructure failure
   (host, disk or provider), restore the newest point with `--live-database-lost`; the result is UNVERIFIED and the
   record says so. After a compromise, the newest point may already hold the attacker's changes; the owner decides
   between restoring and starting a fresh database.
4. **Drill.** Monthly, and after any change to the tooling, the key or the drive: `cth_backup_scheduled.py drill` restores
   the newest point on the drive with the owner's identity. Record it in `docs/ops/audits/RESTORE_DRILL_<date>.md`.

## XI. Owner decisions

Plan §7 and §8 give the background.

| # | Decision | Proposed | Plan ref |
|---|---|---|---|
| D1 | Placement: operator's computer + drive, droplet + B2 bucket, or both | **Settled 2026-11-25:** the operator's computer + SSD, with the existing `cth_db_backup.py`; macOS or Linux | §3.6, F1 |
| D2 | Points kept | **Settled 2026-11-25:** one copy of the newest verified point (§VIII.1) | §7.2, F4, F6 |
| D3 | Drive unlocks from the keychain unattended | **Settled 2026-11-25:** yes (the keychain on macOS, a `/etc/crypttab` key file on Linux), so a purge never waits for a manual unlock | new |
| D4 | Longest a pre-destruction point may survive (computer asleep, drive detached, baseline failing) | **Settled 2026-11-25:** nothing beyond the job itself. It deletes outdated points, a failed run notifies, and the owner deletes by hand any it could not. A solo-maintained project, not a service: no deadline | F2, F3 |
| D5 | Pre-release points | **Settled 2026-11-25:** §VIII.3. The 14 older ones in `~/cth-backup/` were deleted the same day | new |
| D6 | Second `age` recipient kept offline | **Settled 2026-11-25:** three recipients, the owner's key (password manager) and two YubiKeys (`age-plugin-yubikey`), one kept away from the computer | F7 |
| D7 | Application secrets stored off the droplet, apart from the drive | **Settled 2026-11-25:** in the owner's password manager | F8 |
| D8 | Deletions other than seat, class or user (expired recovery codes, cleared claim hashes) | **Settled 2026-11-25:** accepted when captured. Time-bound codes carry their expiry, so a restored expired code must still be refused | F4 |
| D9 | Restoring after total loss without the no-resurrection check | **Settled 2026-11-25:** by cause (§X.3) | F6 |
| D10 | Alerting beyond desktop notifications | **Settled 2026-11-25:** notifications only | F5 |
| D11 | Computer loss or compromise: it holds root SSH to production and the read-only role's password; drive and points are ciphertext | **Settled 2026-11-25:** accepted; a lost or compromised Mac is a wider incident than backups | new |

## XII. Evidence and records

- Install: an ops record with the date, first stem, drill result and drive listing.
- Drills: `docs/ops/audits/RESTORE_DRILL_<date>.md`.
- Releases: `SOP-DEP-002` §VII.A as now; a scheduled point does not replace the pre-release point.
- Records name no class, seat or user ids.

---

## Change Notes

**Version 1.0 (2026-11-25):** First issue, effective on issue (owner ruling). Places the existing `cth_db_backup.py`
on the operator's computer (macOS or Linux, `cth_backup_scheduled.py` under launchd or systemd) with an encrypted
external drive as the off-host copy. Records the owner's rulings on the eleven decisions issue #1639's failure-mode
review required (§XI), including one copy of the newest verified point, whatever took it (§VIII).
