#!/usr/bin/env python3
"""Scheduled encrypted backups from the operator's computer to an encrypted external drive.

    cth_backup_scheduled.py backup   # nightly point
    cth_backup_scheduled.py check    # every 15 minutes: replacement baseline after a protected destruction
    cth_backup_scheduled.py status   # health: CURRENT / STALE / DEGRADED (exit 0 / 1 / 2)
    cth_backup_scheduled.py drill    # restore drill: newest point on the drive, decrypted with the identity in
                                     # ~/cth-backup/identity.txt (deleted on exit), restored and checked

Runs ``cth_db_backup.py`` (same directory) with the drive as its off-host copy, on macOS or Linux. The scheduler
is the platform's own: launchd (``macos/``) or systemd user units (``linux/``). Governed by SOP-DB-005;
install steps in ``README.md``. Uses its own tunnel port, verify container and state directory, so it never
touches what ``prerelease.sh`` owns.

Needs: Python 3.9+, ``ssh``, ``docker`` (any engine), ``pg_isready``/``pg_dump``/``pg_restore`` of the server's
major (14), ``age``, ``rclone``. Settings come from the environment, then ``~/cth-backup/scheduled/env``
(``KEY=VALUE`` lines), then the defaults below.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
ROOT = HOME / "cth-backup"
BASE = ROOT / "scheduled"
IDENTITY = ROOT / "identity.txt"
TOOL = Path(__file__).resolve().with_name("cth_db_backup.py")
CONTAINER = "cth-sched-verify"
REDACT = re.compile(r"postgresql://\S*@")
STAMP = re.compile(r"^cth-db-(\d{8}T\d{6}Z)-\w+\.manifest\.json$")
LOCK_WAIT = {"backup": 1800, "drill": 600}  # a check finding the lock taken just exits; the next is 15 minutes away
EX_TEMPFAIL = 75

DEFAULT_DRIVE = {"darwin": "/Volumes/CTH-Backup"}.get(sys.platform, f"/media/{os.environ.get('USER', '')}/CTH-Backup")


def settings(env=os.environ):
    file_values = {}
    with contextlib.suppress(FileNotFoundError):
        for line in (BASE / "env").read_text().splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#"):
                file_values[key.strip()] = value.strip()

    def get(key, default):
        return env.get(key) or file_values.get(key) or default

    return {
        "drive": Path(get("CTH_BACKUP_DRIVE", DEFAULT_DRIVE)),
        "ssh_host": get("CTH_BACKUP_SSH_HOST", "root@cth"),
        "service": get("CTH_BACKUP_APP_SERVICE", "classroom-economy"),
        "tunnel_port": int(get("CTH_BACKUP_TUNNEL_PORT", "55435")),  # prerelease.sh: 55433 tunnel, 55432 verify
        "verify_port": int(get("CTH_BACKUP_VERIFY_PORT", "55436")),
        "pg_bin": get("CTH_BACKUP_PG_BIN", ""),
    }


def log(cmd, msg):
    print(f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} cth-backup-scheduled {cmd}: {msg}", flush=True)


def notify(msg):
    """Best effort: a desktop notification where the platform has one. The log and exit code are the record."""
    with contextlib.suppress(Exception):
        if sys.platform == "darwin":
            subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "CTH database backup"'],
                           capture_output=True, timeout=10)
        elif shutil.which("notify-send"):
            subprocess.run(["notify-send", "CTH database backup", msg], capture_output=True, timeout=10)


@contextlib.contextmanager
def keep_awake():
    """Hold off system sleep for the run: after a scheduled wake the system sleeps again within minutes."""
    if sys.platform == "darwin":
        cmd = ["caffeinate", "-i", "-w", str(os.getpid())]
    elif shutil.which("systemd-inhibit"):
        cmd = ["systemd-inhibit", "--what=sleep", "--why=CTH database backup", "sleep", "86400"]
    else:
        cmd = None
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) if cmd and shutil.which(cmd[0]) else None
    try:
        yield
    finally:
        if proc:
            proc.terminate()


@contextlib.contextmanager
def run_lock(wait):
    BASE.mkdir(parents=True, exist_ok=True)
    with open(BASE / "wrapper.lock", "w") as fh:
        deadline = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SystemExit(EX_TEMPFAIL)
                time.sleep(5)
        yield


def drive_mounted(path):
    # A folder left at the mount point while the drive is away is the system disk, not the drive.
    return os.path.ismount(path)


# --------------------------------------------------------------------------- one copy (SOP-DB-005 §VIII)


def newest_stamp(folder):
    """Newest verified point's UTC stamp in a folder of points ("" when none). A manifest marks a verified point."""
    with contextlib.suppress(FileNotFoundError, NotADirectoryError):
        return max((m.group(1) for n in os.listdir(folder) if (m := STAMP.match(n))), default="")
    return ""


def prerelease_folders():
    return sorted(p for p in ROOT.glob("prerelease-*") if p.is_dir())


def drop_older_prerelease(stamp, out):
    for folder in prerelease_folders():
        if newest_stamp(folder / "points") >= stamp:  # "" (an abandoned run) sorts first
            continue
        # A pre-release run in progress holds its folder's run.lock (cth_db_backup.py) and may have no point yet.
        with open(folder / "run.lock", "a") as fh:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                out(f"kept {folder}: a pre-release run holds it")
                continue
            shutil.rmtree(folder)
        out(f"deleted older point folder {folder}")


def adopt_identities(folder, state_dir):
    """The destruction check compares production with the newest point's identities; make that the pre-release one.

    Off the drive, so status reports DEGRADED until the next nightly point replaces it (SOP-DB-005 §IX).
    """
    newest = json.loads((folder / "state.json").read_text())["newest_point"]
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "state.json"
    state = json.loads(path.read_text()) if path.exists() else {}
    state["newest_point"] = {**newest, "off_host": False}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    os.replace(tmp, path)


def one_copy(remote, state_dir, out):
    """Owner ruling 2026-11-25: one copy of one point exists, the newest verified one, whatever took it.

    A point on the drive is verified once its manifest is there. A pre-release point is verified once its restore
    passed (restore.ok). The newest of them stays; everything else goes, including the tool's copy on this computer.
    """
    drive = newest_stamp(remote)
    pre, pre_folder = max(((newest_stamp(f / "points"), f) for f in prerelease_folders()
                           if (f / "restore.ok").exists()), default=("", None))
    if pre and pre > drive:
        for name in os.listdir(remote):
            if name.startswith("cth-db-"):
                (remote / name).unlink()
                out(f"deleted the drive's point {name}: pre-release point {pre} is newer")
        adopt_identities(pre_folder, state_dir)
    elif drive:
        drop_older_prerelease(drive, out)
    with contextlib.suppress(FileNotFoundError):
        for name in os.listdir(state_dir / "points"):
            if name.startswith("cth-db-"):
                (state_dir / "points" / name).unlink()


# --------------------------------------------------------------------------- production and the verify database


@contextlib.contextmanager
def tunnel(cfg):
    """`ssh -L` to production for the length of the run. BatchMode: a key needing a prompt fails, never hangs."""
    # Something else on the port would be connected to as production with the stored credentials.
    if port_open(cfg["tunnel_port"]):
        raise RuntimeError(f"port {cfg['tunnel_port']} is already in use; the tunnel was not opened")
    proc = subprocess.Popen(["ssh", "-N", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
                             "-L", f"{cfg['tunnel_port']}:127.0.0.1:5432", cfg["ssh_host"]])
    try:
        deadline = time.monotonic() + 30
        while not port_open(cfg["tunnel_port"]):
            if proc.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("tunnel to production did not come up")
            time.sleep(0.5)
        if proc.poll() is not None:
            raise RuntimeError("tunnel to production did not come up")
        yield
    finally:
        proc.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=10)


def port_open(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def app_active(cfg):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", cfg["ssh_host"],
                           f"systemctl is-active --quiet {cfg['service']}"]).returncode == 0


@contextlib.contextmanager
def verify_container(cfg, databases):
    """A throwaway PostgreSQL 14 with its data on tmpfs: removing it erases the plaintext it held."""
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0 and shutil.which("colima"):
        subprocess.run(["colima", "start"], capture_output=True)  # shortcut: leaves colima running afterwards
    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
    try:
        subprocess.run(["docker", "run", "--rm", "-d", "--name", CONTAINER, "-e", "POSTGRES_PASSWORD=verify",
                        "-p", f"127.0.0.1:{cfg['verify_port']}:5432", "--tmpfs", "/var/lib/postgresql/data",
                        "postgres:14"], check=True, capture_output=True)
        ready = ["pg_isready", "-h", "127.0.0.1", "-p", str(cfg["verify_port"]), "-U", "postgres"]
        for _ in range(30):
            if subprocess.run(ready, capture_output=True).returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("verify container did not become ready")
        for name in databases:
            subprocess.run(["docker", "exec", CONTAINER, "createdb", "-U", "postgres", name], check=True)
        yield f"postgresql://postgres:verify@127.0.0.1:{cfg['verify_port']}"
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)


def run_tool(args, env):
    proc = subprocess.Popen([sys.executable, str(TOOL), *args], env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        sys.stdout.write(REDACT.sub("postgresql://[redacted]@", line))
    return proc.wait()


# --------------------------------------------------------------------------- main


def run(cmd, cfg):
    def out(msg):
        log(cmd, msg)

    remote = cfg["drive"] / "cth-db-backups" / "production"
    state_dir = BASE / "state"
    if not drive_mounted(cfg["drive"]):
        out(f"{cfg['drive']} is not mounted; nothing done")
        if cmd == "backup":  # a check every 15 minutes saying so would be noise
            notify("Nightly backup skipped: the backup drive is not attached and unlocked.")
        return 1 if cmd == "status" else 0
    remote.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    path = [cfg["pg_bin"]] if cfg["pg_bin"] else []
    env["PATH"] = os.pathsep.join(path + ["/opt/homebrew/bin", "/usr/local/bin", env.get("PATH", "/usr/bin:/bin")])
    colima_sock = HOME / ".colima" / "default" / "docker.sock"
    if "DOCKER_HOST" not in env and colima_sock.exists():
        env["DOCKER_HOST"] = f"unix://{colima_sock}"
    os.environ.update(PATH=env["PATH"], **({"DOCKER_HOST": env["DOCKER_HOST"]} if "DOCKER_HOST" in env else {}))
    env.update(
        CTH_BACKUP_STATE_DIR=str(state_dir),
        CTH_BACKUP_REMOTE=str(remote),
        # Owner ruling 2026-11-25 (SOP-DB-005 §VIII): one point; one_copy() removes the local copy after.
        CTH_BACKUP_KEEP_REMOTE="1",
        CTH_BACKUP_KEEP_LOCAL="1",
        CTH_BACKUP_AGE_RECIPIENTS_FILE=str(ROOT / "recipients.txt"),
    )

    with tunnel(cfg):
        # A stopped application means a release (prerelease.sh stops it; the release restarts it after migrating)
        # or an outage. A backup then could hold locks a migration needs (plan §8 F10), so do nothing.
        if not app_active(cfg):
            out(f"{cfg['service']} is not active (release or outage in progress); nothing done")
            if cmd == "backup":
                notify("Nightly backup skipped: the application is stopped.")
            # Skipping is success only for the scheduled runs; a drill or status that did not run must not pass.
            return 0 if cmd in ("backup", "check") else 1
        env["CTH_BACKUP_SOURCE_URL"] = (BASE / "source_url").read_text().strip()

        if cmd == "status":
            return run_tool(["status"], env)

        if cmd == "drill":
            if not IDENTITY.exists():
                out(f"missing {IDENTITY}")
                return 1
            points = sorted(remote.glob("cth-db-*.dump.age"))
            if not points:
                out("no point on the drive")
                return 1
            artifact = points[-1]
            with verify_container(cfg, ["cth_backup_verify", "cth_restore_check"]) as pg:
                env["CTH_BACKUP_VERIFY_URL"] = f"{pg}/cth_backup_verify"
                return run_tool(["restore", "--artifact", str(artifact),
                                 "--manifest", str(artifact).removesuffix(".dump.age") + ".manifest.json",
                                 "--identity", str(IDENTITY), "--target-url", f"{pg}/cth_restore_check",
                                 "--live-url", env["CTH_BACKUP_SOURCE_URL"]], env)

        with verify_container(cfg, ["cth_backup_verify"]) as pg:
            env["CTH_BACKUP_VERIFY_URL"] = f"{pg}/cth_backup_verify"
            out("start")
            rc = run_tool([cmd], env)
    if rc == 0:
        one_copy(remote, state_dir, out)
        out("done")
    return rc


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] not in ("backup", "check", "status", "drill"):
        print(f"usage: {Path(sys.argv[0]).name} backup|check|status|drill")
        return 2
    cmd = argv[0]
    cfg = settings()
    rc = 1
    try:
        with run_lock(LOCK_WAIT.get(cmd, 0)), keep_awake():
            rc = run(cmd, cfg)
    except SystemExit as exc:
        if exc.code == EX_TEMPFAIL:
            log(cmd, "another run holds the lock; nothing done")
            return EX_TEMPFAIL
        raise
    except Exception as exc:  # recorded and notified; the exit code tells the scheduler
        log(cmd, f"error: {REDACT.sub('postgresql://[redacted]@', str(exc))}")
        rc = 1
    finally:
        if cmd == "drill" and IDENTITY.exists():
            IDENTITY.unlink()
            log(cmd, "identity deleted")
    if rc != 0 and cmd != "status":
        log(cmd, f"failed (exit {rc})")
        notify(f"{cmd} failed (exit {rc}). See the backup log.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
