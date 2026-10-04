#!/usr/bin/env python3
"""Encrypted off-host PostgreSQL backups with a post-destruction baseline rule.

PROPOSAL, NOT APPLIED. See ``infra/db-backup/README.md`` and
``docs/ops/DATABASE_BACKUP_PLAN.md``. The baseline model this implements is the
owner's 2026-09-30 direction (POST_LAUNCH_TRACKER_2026.md §IV-B), which is still
under failure-mode review; nothing here is normative.

Commands
--------
backup   Take one recovery point: snapshot-consistent ``pg_dump``, encrypted with
         ``age`` to a public recipient, restored into a scratch database and
         checked row-for-row against counts taken inside the same snapshot,
         uploaded off-host and re-hashed there, then retention applied.
check    Cheap hourly probe. If any seat, class or user present in the newest
         recovery point is gone from the live database, a protected
         destruction has happened since: take a replacement baseline now.
status   Report baseline health: CURRENT, STALE or DEGRADED (exit 0, 1, 2).
restore  Decrypt a recovery point into an EMPTY database and verify it. Never
         touches the live database and never cuts over.

The baseline rule
-----------------
A destruction is detected as "an identity row in the newest verified point is
missing from the snapshot now being taken". Every point older than the newest
verified point taken after a destruction is unacceptable and is deleted, local
and off-host, but only after that replacement point has been verified. Until
then the old points are kept and health is STALE.

The host holds only the age *recipient* (public key). It cannot decrypt any
recovery point; the identity lives with the owner, off the droplet.

Dependencies: python3, psycopg2, pg_dump/pg_restore (same major as the server
and the verify database; a newer pg_dump writes settings an older server
rejects), age, rclone. No application code is imported, so the job needs none of the
application's secrets.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg2

# Identity rows whose disappearance is a protected destruction (seat, class or
# teacher-account deletion; user rows go with the last seat of a student and with
# a destroyed teacher account, INV-CORE-000 §III.5).
IDENTITY_QUERIES = {
    "seats": "SELECT id::text FROM public.seats",
    "classes": "SELECT class_id::text FROM public.classes",
    "users": "SELECT id::text FROM public.users",
}

POINT_RE = re.compile(r"^cth-db-(\d{8}T\d{6}Z)-(scheduled|baseline|manual)\.(dump\.age|manifest\.json)$")
CHUNK = 1024 * 1024

HEALTH_EXIT = {"CURRENT": 0, "STALE": 1, "DEGRADED": 2}


# --------------------------------------------------------------------------- config


class Config:
    def __init__(self, env=os.environ):
        def req(name):
            value = env.get(name, "").strip()
            if not value:
                raise SystemExit(f"cth-db-backup: {name} is not set")
            return value

        self._req = req
        self.env = env
        self.state_dir = Path(env.get("CTH_BACKUP_STATE_DIR", "/var/lib/cth-db-backup"))
        self.points_dir = self.state_dir / "points"
        self.keep_remote = int(env.get("CTH_BACKUP_KEEP_REMOTE", "14"))
        self.keep_local = int(env.get("CTH_BACKUP_KEEP_LOCAL", "2"))
        self.max_age_hours = float(env.get("CTH_BACKUP_MAX_AGE_HOURS", "26"))
        self.exclude_table_data = [
            t.strip() for t in env.get("CTH_BACKUP_EXCLUDE_TABLE_DATA", "teacher_signup_attempts").split(",") if t.strip()
        ]
        self.lock_wait_timeout = env.get("CTH_BACKUP_LOCK_WAIT_TIMEOUT", "60s")

    # Required only by the commands that use them.
    @property
    def source_url(self):
        return self._req("CTH_BACKUP_SOURCE_URL")

    @property
    def verify_url(self):
        return self._req("CTH_BACKUP_VERIFY_URL")

    @property
    def recipients_file(self):
        return self._req("CTH_BACKUP_AGE_RECIPIENTS_FILE")

    @property
    def remote(self):
        """Off-host target, or None for a local-only run (the pre-release run)."""
        value = self.env.get("CTH_BACKUP_REMOTE", "").strip().rstrip("/")
        return value or None

    @property
    def rclone_base(self):
        cmd = ["rclone"]
        conf = self.env.get("CTH_BACKUP_RCLONE_CONFIG", "").strip()
        if conf:
            cmd += ["--config", conf]
        return cmd


def log(msg):
    print(f"cth-db-backup: {msg}", flush=True)


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def stamp(ts):
    return ts.strftime("%Y%m%dT%H%M%SZ")


def parse_stamp(s):
    return dt.datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)


# --------------------------------------------------------------------------- state


def load_state(cfg):
    path = cfg.state_dir / "state.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_state(cfg, state):
    path = cfg.state_dir / "state.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    os.replace(tmp, path)


class LockBusy(SystemExit):
    """Another run holds the lock. A SystemExit, so an unhandled one exits non-zero."""


@contextlib.contextmanager
def run_lock(cfg):
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    with open(cfg.state_dir / "run.lock", "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LockBusy("cth-db-backup: another run holds the lock")
        yield


# --------------------------------------------------------------------------- database


def identity_sets(cur):
    out = {}
    for name, sql in IDENTITY_QUERIES.items():
        cur.execute(sql)
        out[name] = sorted(r[0] for r in cur.fetchall())
    return out


def table_counts(cur):
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
    tables = [r[0] for r in cur.fetchall()]
    counts = {}
    for t in tables:
        cur.execute(f'SELECT count(*) FROM public."{t}"')
        counts[t] = cur.fetchone()[0]
    return counts


def alembic_revision(cur):
    cur.execute("SELECT version_num FROM public.alembic_version")
    rows = sorted(r[0] for r in cur.fetchall())
    return ",".join(rows)


def missing_identities(previous, current):
    """Identity ids present in ``previous`` but absent from ``current``, per kind."""
    gone = {}
    for kind in IDENTITY_QUERIES:
        lost = sorted(set(previous.get(kind, [])) - set(current.get(kind, [])))
        if lost:
            gone[kind] = len(lost)
    return gone


PG_CLIENT_TOOLS = ("pg_dump", "pg_restore")


def parse_pg_major(version_text):
    """Major version from ``pg_dump --version`` style output, e.g. 14 from
    ``pg_dump (PostgreSQL) 14.24 (Ubuntu 14.24-0ubuntu0.22.04.1)``."""
    m = re.search(r"\(PostgreSQL\)\s+(\d+)", version_text)
    if not m:
        raise ValueError(f"unrecognised PostgreSQL version output: {version_text.strip()[:200]!r}")
    return int(m.group(1))


def client_version_mismatches(client_majors, server_majors):
    """Every (client, server) pair whose majors differ. A newer client writes
    settings an older server rejects (pg_dump 17 emits ``SET transaction_timeout``,
    which 14 refuses), so verification would fail after the dump; an older client
    may not read a newer server at all. Only an exact match is accepted."""
    return [f"{tool} is PostgreSQL {cmaj}, {label} is {smaj}"
            for tool, cmaj in sorted(client_majors.items())
            for label, smaj in sorted(server_majors.items())
            if cmaj != smaj]


def server_major(url):
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW server_version_num")
            return int(cur.fetchone()[0]) // 10000
    finally:
        conn.close()


def require_matching_clients(servers):
    """Refuse before any dump or restore unless pg_dump and pg_restore have the
    same major version as every database named in ``servers`` ({label: url})."""
    clients = {tool: parse_pg_major(subprocess.run([tool, "--version"], capture_output=True, text=True,
                                                   check=True).stdout)
               for tool in PG_CLIENT_TOOLS}
    problems = client_version_mismatches(clients, {label: server_major(url) for label, url in servers.items()})
    if problems:
        raise RuntimeError("refusing: PostgreSQL client and server majors differ: " + "; ".join(problems))


def wipe_public_schema(url):
    conn = psycopg2.connect(url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
            cur.execute("CREATE SCHEMA public")
    finally:
        conn.close()


def public_table_count(url):
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
            return cur.fetchone()[0]
    finally:
        conn.close()


def compare_restored(url, manifest, excluded):
    """Return a list of mismatches between a restored database and a manifest."""
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            restored = table_counts(cur)
            rev = alembic_revision(cur)
    finally:
        conn.close()
    problems = []
    expected = dict(manifest["table_counts"])
    for t in excluded:
        if t in expected:
            expected[t] = 0
    if set(restored) != set(expected):
        problems.append(f"table set differs: missing {sorted(set(expected) - set(restored))}, "
                        f"extra {sorted(set(restored) - set(expected))}")
    for t in sorted(set(restored) & set(expected)):
        if restored[t] != expected[t]:
            problems.append(f"{t}: restored {restored[t]} rows, snapshot had {expected[t]}")
    if rev != manifest["alembic_revision"]:
        problems.append(f"alembic revision {rev!r} != manifest {manifest['alembic_revision']!r}")
    return problems


# --------------------------------------------------------------------------- remote


def rclone(cfg, *args, capture=False):
    cmd = cfg.rclone_base + list(args)
    if capture:
        return subprocess.run(cmd, check=True, stdout=subprocess.PIPE, text=True).stdout
    subprocess.run(cmd, check=True)


def remote_sha256(cfg, name):
    proc = subprocess.Popen(cfg.rclone_base + ["cat", f"{cfg.remote}/{name}"], stdout=subprocess.PIPE)
    h = hashlib.sha256()
    for chunk in iter(lambda: proc.stdout.read(CHUNK), b""):
        h.update(chunk)
    if proc.wait() != 0:
        raise RuntimeError(f"rclone cat {name} failed")
    return h.hexdigest()


def remote_names(cfg):
    out = rclone(cfg, "lsf", "--files-only", cfg.remote, capture=True)
    return [line.strip() for line in out.splitlines() if line.strip()]


def points_from_names(names):
    """Group file names into recovery points keyed by stem, with their parts."""
    points = {}
    for n in names:
        m = POINT_RE.match(n)
        if not m:
            continue
        stem = f"cth-db-{m.group(1)}-{m.group(2)}"
        p = points.setdefault(stem, {"stem": stem, "taken_at": parse_stamp(m.group(1)), "reason": m.group(2), "files": []})
        p["files"].append(n)
    return points


# --------------------------------------------------------------------------- backup


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def dump_encrypt_and_verify(cfg, snapshot_id, out_path, err_dir):
    """Stream one pg_dump into age (to disk) and pg_restore (into the scratch db).

    Both consumers receive the identical byte stream, so a verified restore of
    the plaintext proves the ciphertext's content without the host ever holding
    the decryption identity. No plaintext is written to disk.
    """
    dump_cmd = ["pg_dump", "--format=custom", f"--snapshot={snapshot_id}",
                f"--lock-wait-timeout={cfg.lock_wait_timeout}", "--dbname", cfg.source_url]
    for t in cfg.exclude_table_data:
        dump_cmd.append(f"--exclude-table-data=public.{t}")
    age_cmd = ["age", "--encrypt", "-R", cfg.recipients_file, "-o", str(out_path)]
    restore_cmd = ["pg_restore", "--no-owner", "--no-privileges", "--exit-on-error", "--dbname", cfg.verify_url]

    errs = {k: open(err_dir / f"{k}.err", "w+") for k in ("pg_dump", "age", "pg_restore")}
    dump = subprocess.Popen(dump_cmd, stdout=subprocess.PIPE, stderr=errs["pg_dump"])
    age = subprocess.Popen(age_cmd, stdin=subprocess.PIPE, stderr=errs["age"])
    restore = subprocess.Popen(restore_cmd, stdin=subprocess.PIPE, stderr=errs["pg_restore"])
    broken = set()
    try:
        for chunk in iter(lambda: dump.stdout.read(CHUNK), b""):
            for name, proc in (("age", age), ("pg_restore", restore)):
                if name in broken:
                    continue
                try:
                    proc.stdin.write(chunk)
                except BrokenPipeError:
                    broken.add(name)
    finally:
        for proc in (age, restore):
            with contextlib.suppress(BrokenPipeError):
                proc.stdin.close()
    codes = {"pg_dump": dump.wait(), "age": age.wait(), "pg_restore": restore.wait()}
    failed = {k: v for k, v in codes.items() if v != 0}
    if failed or broken:
        detail = []
        for k in failed:
            errs[k].seek(0)
            detail.append(f"{k} exited {failed[k]}: {errs[k].read().strip()[-2000:]}")
        raise RuntimeError("dump pipeline failed; " + "; ".join(detail or [f"broken pipe to {sorted(broken)}"]))


def cmd_backup(cfg, reason="scheduled", forced_baseline=False):
    with run_lock(cfg):
        return _backup(cfg, reason, forced_baseline)


def _backup(cfg, reason, forced_baseline):
    cfg.points_dir.mkdir(parents=True, exist_ok=True)
    state = load_state(cfg)
    state["last_run"] = {"started_at": utcnow().isoformat(), "ok": False, "reason": reason}
    save_state(cfg, state)

    try:
        require_matching_clients({"source database": cfg.source_url, "verify database": cfg.verify_url})
        src = psycopg2.connect(cfg.source_url)
        try:
            src.set_session(isolation_level="REPEATABLE READ", readonly=True)
            with src.cursor() as cur:
                cur.execute("SELECT pg_export_snapshot(), now(), current_setting('server_version')")
                snapshot_id, taken_at, server_version = cur.fetchone()
                counts = table_counts(cur)
                revision = alembic_revision(cur)
                ids = identity_sets(cur)

                previous = state.get("newest_point")
                gone = missing_identities(previous["identities"], ids) if previous else {}
                # No record of the previous point's identities while points exist
                # (state lost): treat as a baseline so nothing older can survive it.
                unknown_history = previous is None and bool(
                    points_from_names(os.listdir(cfg.points_dir))
                    or (cfg.remote and points_from_names(remote_names(cfg))))
                is_baseline = forced_baseline or bool(gone) or unknown_history
                if is_baseline:
                    reason = "baseline" if reason == "scheduled" else reason
                    log(f"protected destruction detected since last point ({gone or 'history unknown'}); "
                        "this point becomes the replacement baseline")

                stem = f"cth-db-{stamp(taken_at.astimezone(dt.timezone.utc))}-{reason}"
                artifact = cfg.points_dir / f"{stem}.dump.age"
                tmp_artifact = artifact.with_suffix(".age.partial")

                wipe_public_schema(cfg.verify_url)
                try:
                    with tempfile.TemporaryDirectory(dir=cfg.state_dir) as err_dir:
                        dump_encrypt_and_verify(cfg, snapshot_id, tmp_artifact, Path(err_dir))
                    manifest = {
                        "format": 1,
                        "stem": stem,
                        "reason": reason,
                        "baseline": is_baseline,
                        "taken_at": taken_at.astimezone(dt.timezone.utc).isoformat(),
                        "server_version": server_version,
                        "alembic_revision": revision,
                        "excluded_table_data": cfg.exclude_table_data,
                        "table_counts": counts,
                        "identity_counts": {k: len(v) for k, v in ids.items()},
                    }
                    problems = compare_restored(cfg.verify_url, manifest, cfg.exclude_table_data)
                finally:
                    # The scratch database held plaintext; it never outlives the run.
                    wipe_public_schema(cfg.verify_url)
            src.commit()  # release the snapshot only after pg_dump has finished with it
        finally:
            src.close()

        if problems:
            tmp_artifact.unlink(missing_ok=True)
            raise RuntimeError("restore verification failed: " + "; ".join(problems))

        os.replace(tmp_artifact, artifact)
        manifest["artifact_sha256"] = sha256_file(artifact)
        manifest["artifact_bytes"] = artifact.stat().st_size
        manifest_path = cfg.points_dir / f"{stem}.manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
        log(f"{stem}: verified locally ({sum(counts.values())} rows in {len(counts)} tables)")

        # Off-host copy. The manifest goes last: a point is complete off-host only
        # when its manifest is there and its artifact re-hashes to the manifest.
        if cfg.remote:
            rclone(cfg, "copyto", str(artifact), f"{cfg.remote}/{artifact.name}")
            if remote_sha256(cfg, artifact.name) != manifest["artifact_sha256"]:
                raise RuntimeError(f"{artifact.name}: off-host copy does not match local hash")
            try:
                rclone(cfg, "copyto", str(manifest_path), f"{cfg.remote}/{manifest_path.name}")
            except Exception:
                # An artifact without its manifest is never a complete point.
                with contextlib.suppress(Exception):
                    rclone(cfg, "deletefile", f"{cfg.remote}/{artifact.name}")
                raise
            log(f"{stem}: off-host copy verified")
        else:
            log(f"{stem}: CTH_BACKUP_REMOTE unset, local-only point")

        state.setdefault("points", [])
        state["points"] = [p for p in state["points"] if p != stem] + [stem]
        state["newest_point"] = {"stem": stem, "taken_at": manifest["taken_at"], "identities": ids,
                                 "off_host": bool(cfg.remote)}
        if is_baseline:
            state["baseline_at"] = manifest["taken_at"]
            state["baseline_stem"] = stem
        save_state(cfg, state)

        apply_retention(cfg, state)
        if cfg.remote:
            audit_remote(cfg)
        state["last_run"].update({"ok": True, "finished_at": utcnow().isoformat(), "stem": stem})
        state.pop("last_error", None)
        save_state(cfg, state)
        log(f"{stem}: done; health {compute_health(cfg, state)['health']}")
        return 0
    except Exception as exc:  # recorded for status, then re-raised for systemd
        for leftover in cfg.points_dir.glob("*.partial"):
            leftover.unlink()
        state["last_error"] = {"at": utcnow().isoformat(), "error": str(exc)[:2000]}
        save_state(cfg, state)
        raise


def apply_retention(cfg, state):
    """Delete points older than the baseline, then all but the newest N.

    Runs off-host first, then locally. It only ever deletes points older than
    ``newest_point``, which by this time is verified off-host.
    """
    newest = state["newest_point"]["stem"]
    baseline_at = dt.datetime.fromisoformat(state["baseline_at"]) if state.get("baseline_at") else None

    def doomed(points, keep):
        ordered = sorted(points.values(), key=lambda p: p["taken_at"], reverse=True)
        out = []
        for i, p in enumerate(ordered):
            if p["stem"] == newest:
                continue
            if baseline_at and p["taken_at"] < baseline_at.replace(microsecond=0):
                out.append(p)  # predates a protected destruction: unacceptable
            elif i >= keep:
                out.append(p)
        return out

    remote_points = points_from_names(remote_names(cfg)) if cfg.remote else {}
    # A point missing its manifest or artifact (an interrupted upload or
    # deletion) is not a recovery point: remove it before counting retention.
    for stem, p in list(remote_points.items()):
        if len(p["files"]) != 2 and stem != newest:
            for name in sorted(p["files"], key=lambda n: n.endswith(".manifest.json")):
                rclone(cfg, "deletefile", f"{cfg.remote}/{name}")
            log(f"{stem}: removed incomplete off-host point")
            del remote_points[stem]
    for p in doomed(remote_points, cfg.keep_remote):
        # Artifact first, manifest last, so a half-deleted point is never "complete".
        for name in sorted(p["files"], key=lambda n: n.endswith(".manifest.json")):
            rclone(cfg, "deletefile", f"{cfg.remote}/{name}")
        log(f"{p['stem']}: deleted off-host")

    local_points = points_from_names(os.listdir(cfg.points_dir))
    for p in doomed(local_points, cfg.keep_local):
        for name in p["files"]:
            (cfg.points_dir / name).unlink(missing_ok=True)
        log(f"{p['stem']}: deleted locally")

    for leftover in cfg.points_dir.glob("*.partial"):
        leftover.unlink()

    kept = points_from_names(remote_names(cfg)) if cfg.remote else points_from_names(os.listdir(cfg.points_dir))
    state["points"] = sorted(kept)


def audit_remote(cfg):
    """Re-hash every retained off-host point against its manifest."""
    with tempfile.TemporaryDirectory(dir=cfg.state_dir) as tmp:
        for stem, p in sorted(points_from_names(remote_names(cfg)).items()):
            mname = f"{stem}.manifest.json"
            aname = f"{stem}.dump.age"
            if mname not in p["files"] or aname not in p["files"]:
                raise RuntimeError(f"{stem}: incomplete off-host point {p['files']}")
            rclone(cfg, "copyto", f"{cfg.remote}/{mname}", f"{tmp}/{mname}")
            manifest = json.loads(Path(tmp, mname).read_text())
            if remote_sha256(cfg, aname) != manifest["artifact_sha256"]:
                raise RuntimeError(f"{stem}: off-host artifact no longer matches its manifest")


# --------------------------------------------------------------------------- check / status


def live_identities(cfg):
    conn = psycopg2.connect(cfg.source_url)
    try:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            return identity_sets(cur)
    finally:
        conn.close()


def cmd_check(cfg):
    """Runs entirely under the run lock, so it cannot race the nightly backup."""
    try:
        with run_lock(cfg):
            return _check(cfg)
    except LockBusy:
        log("a backup is running; it performs the same check")
        return 0


def _check(cfg):
    # A run that crashed may have left plaintext in the scratch database.
    if public_table_count(cfg.verify_url):
        log("scratch database not empty (an earlier run was interrupted); emptying it")
        wipe_public_schema(cfg.verify_url)
    state = load_state(cfg)
    previous = state.get("newest_point")
    if previous is None:
        log("no verified point yet; taking one")
        return _backup(cfg, "baseline", True)
    gone = missing_identities(previous["identities"], live_identities(cfg))
    if gone:
        log(f"protected destruction detected ({gone}); taking a replacement baseline")
        return _backup(cfg, "baseline", True)
    if state.get("last_error"):
        # The newest point is verified, but the run that made it may have
        # stopped before its purge or audit finished. Finish them now rather than
        # leaving pre-destruction points off-host until the next nightly run.
        log("previous run did not finish; retrying retention and the off-host audit")
        try:
            apply_retention(cfg, state)
            if cfg.remote:
                audit_remote(cfg)
        except Exception as exc:
            state["last_error"] = {"at": utcnow().isoformat(), "error": str(exc)[:2000]}
            save_state(cfg, state)
            raise
        state.pop("last_error", None)
        save_state(cfg, state)
        log("retention and audit completed")
        return 0
    log("no protected destruction since the newest point")
    return 0


def compute_health(cfg, state, live=None):
    reasons = []
    degraded = []
    newest = state.get("newest_point")
    if not newest:
        return {"health": "STALE", "reasons": ["no verified recovery point exists"]}
    age_h = (utcnow() - dt.datetime.fromisoformat(newest["taken_at"])).total_seconds() / 3600
    if age_h > cfg.max_age_hours:
        reasons.append(f"newest point is {age_h:.1f}h old (limit {cfg.max_age_hours}h)")
    if live is not None:
        gone = missing_identities(newest["identities"], live)
        if gone:
            reasons.append(f"protected destruction since newest point, no replacement baseline yet: {gone}")
    if not newest.get("off_host"):
        degraded.append("newest point has no off-host copy")
    if state.get("last_error"):
        degraded.append(f"last run failed: {state['last_error']['error'][:300]}")
    if state.get("baseline_at"):
        baseline_at = dt.datetime.fromisoformat(state["baseline_at"]).replace(microsecond=0)
        older = [s for s in state.get("points", []) if parse_stamp(POINT_RE.match(s + ".manifest.json").group(1)) < baseline_at]
        if older:
            degraded.append(f"points older than the baseline still held: {older}")
    health = "STALE" if reasons else ("DEGRADED" if degraded else "CURRENT")
    return {"health": health, "reasons": reasons + degraded, "newest_point": newest["stem"],
            "baseline": state.get("baseline_stem"), "points": state.get("points", [])}


def cmd_status(cfg, offline=False):
    state = load_state(cfg)
    live = None if offline else live_identities(cfg)
    report = compute_health(cfg, state, live)
    print(json.dumps(report, indent=2))
    return HEALTH_EXIT[report["health"]]


# --------------------------------------------------------------------------- restore


def cmd_restore(cfg, artifact, manifest_path, identity, target_url, live_url, live_database_lost=False):
    if not live_url and not live_database_lost:
        raise SystemExit("refusing: without --live-url nothing can show that this point holds no destroyed seat, "
                         "class or user. Pass --live-url, or --live-database-lost when the live database no "
                         "longer exists (see DATABASE_BACKUP_PLAN.md §5.2, F6)")
    manifest = json.loads(Path(manifest_path).read_text())
    digest = sha256_file(artifact)
    if digest != manifest["artifact_sha256"]:
        raise SystemExit(f"refusing: {artifact} sha256 {digest} does not match its manifest")
    if live_url and live_url == target_url:
        raise SystemExit("refusing: target is the live database")
    if public_table_count(target_url) != 0:
        raise SystemExit("refusing: target database is not empty (restore only into a fresh database)")
    try:
        require_matching_clients({"target database": target_url})
    except RuntimeError as exc:
        raise SystemExit(str(exc))

    age = subprocess.Popen(["age", "--decrypt", "-i", identity, artifact], stdout=subprocess.PIPE)
    restore = subprocess.run(["pg_restore", "--no-owner", "--no-privileges", "--exit-on-error",
                              "--dbname", target_url], stdin=age.stdout)
    age.stdout.close()
    if age.wait() != 0 or restore.returncode != 0:
        raise SystemExit("restore failed; the target database is partial and must be dropped")

    problems = compare_restored(target_url, manifest, manifest.get("excluded_table_data", []))
    if problems:
        raise SystemExit("restored database does not match the manifest: " + "; ".join(problems))
    log(f"{manifest['stem']}: restored and matches its manifest (revision {manifest['alembic_revision']})")

    if live_url:
        conn = psycopg2.connect(target_url)
        try:
            with conn.cursor() as cur:
                restored_ids = identity_sets(cur)
        finally:
            conn.close()
        conn = psycopg2.connect(live_url)
        try:
            conn.set_session(readonly=True)
            with conn.cursor() as cur:
                live_ids = identity_sets(cur)
        finally:
            conn.close()
        resurrected = missing_identities(restored_ids, live_ids)
        if resurrected:
            raise SystemExit(f"REFUSE CUTOVER: the restored database holds identities the live database has "
                             f"destroyed ({resurrected}). Backups must not restore accounts (INV-CORE-000 §III.5). "
                             "Drop the restored database.")
        log("no destroyed seat, class or user would be resurrected")
    else:
        log("UNVERIFIED: the live database is gone, so this point was not checked for destroyed identities. "
            "Nothing available here can prove it holds none; cutover is the owner's decision (plan F6)")
    return 0


# --------------------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cth-db-backup", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--reason", choices=["scheduled", "baseline", "manual"], default="scheduled")
    sub.add_parser("check")
    s = sub.add_parser("status")
    s.add_argument("--offline", action="store_true", help="do not query the live database")
    r = sub.add_parser("restore")
    r.add_argument("--artifact", required=True)
    r.add_argument("--manifest", required=True)
    r.add_argument("--identity", required=True, help="age identity file (owner's key, never on the droplet)")
    r.add_argument("--target-url", required=True, help="an EMPTY database to restore into")
    r.add_argument("--live-url", help="live database, for the no-resurrection check")
    r.add_argument("--live-database-lost", action="store_true",
                   help="the live database no longer exists; restore without the no-resurrection check")
    args = ap.parse_args(argv)
    cfg = Config()

    if args.cmd == "backup":
        return cmd_backup(cfg, reason=args.reason, forced_baseline=args.reason == "baseline")
    if args.cmd == "check":
        return cmd_check(cfg)
    if args.cmd == "status":
        return cmd_status(cfg, offline=args.offline)
    if args.cmd == "restore":
        return cmd_restore(cfg, args.artifact, args.manifest, args.identity, args.target_url, args.live_url,
                           args.live_database_lost)
    return 2


if __name__ == "__main__":
    sys.exit(main())
