"""`infra/db-backup/cth_backup_scheduled.py` runs the backup tool only when it is safe to, and keeps one copy.

SOP-DB-005: the operator's computer (macOS or Linux) runs the runner nightly (`backup`) and hourly
(`check`). It must do nothing while the backup drive is absent or the application is stopped for a release,
and, owner ruling 2026-11-25, exactly one copy of the newest verified point may exist, whatever took it.

The runner is loaded in-process with production, docker and the backup tool replaced, in a throwaway HOME.
Nothing reaches a network or a database.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RUNNER = REPO / "infra" / "db-backup" / "cth_backup_scheduled.py"


@pytest.fixture
def env(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("cth_backup_scheduled", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    root = tmp_path / "cth-backup"
    (root / "scheduled").mkdir(parents=True)
    (root / "scheduled" / "source_url").write_text("postgresql://u:p@127.0.0.1:55435/db\n")
    drive = tmp_path / "drive"
    drive.mkdir()
    monkeypatch.setattr(mod, "ROOT", root)
    monkeypatch.setattr(mod, "BASE", root / "scheduled")
    monkeypatch.setattr(mod, "IDENTITY", root / "identity.txt")
    monkeypatch.setattr(mod, "NIGHTLY_HOUR", -1)  # the suite may run at 03:xx
    monkeypatch.setenv("CTH_BACKUP_DRIVE", str(drive))

    calls = []
    state = {"mounted": True, "active": True, "tool_rc": 0}
    monkeypatch.setattr(mod, "drive_mounted", lambda path: state["mounted"])
    monkeypatch.setattr(mod, "app_active", lambda cfg: state["active"])
    monkeypatch.setattr(mod, "notify", lambda msg: calls.append(("notify", msg)))
    monkeypatch.setattr(mod, "keep_awake", contextlib.nullcontext)

    @contextlib.contextmanager
    def tunnel(cfg):
        calls.append(("tunnel", "open"))
        yield
        calls.append(("tunnel", "closed"))

    @contextlib.contextmanager
    def container(cfg, databases):
        calls.append(("container", "up"))
        yield "postgresql://postgres:verify@127.0.0.1:1"
        calls.append(("container", "removed"))

    def run_tool(args, env):
        calls.append(("tool", args, env["CTH_BACKUP_REMOTE"], env["CTH_BACKUP_KEEP_REMOTE"], env["CTH_BACKUP_KEEP_LOCAL"]))
        return state["tool_rc"]

    monkeypatch.setattr(mod, "tunnel", tunnel)
    monkeypatch.setattr(mod, "verify_container", container)
    monkeypatch.setattr(mod, "run_tool", run_tool)
    remote = drive / "cth-db-backups" / "production"
    return {"mod": mod, "calls": calls, "state": state, "root": root, "drive": drive, "remote": remote}


def kinds(env):
    return [c[0] for c in env["calls"]]


def point(folder, stamp, *, verified_prerelease=False):
    points = folder / "points" if folder.name.startswith("prerelease-") else folder
    points.mkdir(parents=True, exist_ok=True)
    for ext in ("dump.age", "manifest.json"):
        (points / f"cth-db-{stamp}-manual.{ext}").write_text("x")
    if verified_prerelease:
        (folder / "restore.ok").touch()
        (folder / "state.json").write_text(json.dumps({"newest_point": {
            "stem": f"cth-db-{stamp}-manual", "taken_at": stamp, "identities": {"seats": [7]}, "off_host": False}}))


def test_backup_runs_the_tool_against_the_drive_keeping_one_point(env):
    assert env["mod"].main(["backup"]) == 0
    tool = [c for c in env["calls"] if c[0] == "tool"][0]
    assert tool[1:] == (["backup"], str(env["remote"]), "1", "1")
    assert env["calls"][-2:] == [("container", "removed"), ("tunnel", "closed")]
    assert "notify" not in kinds(env)


def test_absent_drive_means_no_run_and_only_the_nightly_says_so(env):
    env["state"]["mounted"] = False
    assert env["mod"].main(["check"]) == 0
    assert env["calls"] == []
    assert env["mod"].main(["backup"]) == 0
    assert kinds(env) == ["notify"]
    assert not env["remote"].exists()


def test_stopped_application_means_no_backup(env):
    env["state"]["active"] = False
    assert env["mod"].main(["backup"]) == 0
    assert "tool" not in kinds(env) and "container" not in kinds(env)
    assert env["calls"][-1] == ("tunnel", "closed")


@pytest.mark.parametrize("cmd", ["drill", "status"])
def test_a_drill_or_status_that_could_not_run_fails(env, cmd):
    """Review on #1873: a skipped drill passed, so the schedule could be enabled with no drill done."""
    point(env["remote"], "20261126T031500Z")
    (env["root"] / "identity.txt").write_text("AGE-SECRET-KEY-FAKE\n")
    env["state"]["active"] = False
    assert env["mod"].main([cmd]) == 1
    assert "tool" not in kinds(env)


def test_the_nightly_hour_takes_no_check(env, monkeypatch):
    """Owner ruling 2026-11-25: 03:15 takes the backup, not a check."""
    import time
    monkeypatch.setattr(env["mod"], "NIGHTLY_HOUR", time.localtime().tm_hour)
    assert env["mod"].main(["check"]) == 0
    assert env["calls"] == []
    assert env["mod"].main(["backup"]) == 0
    assert "tool" in kinds(env)


def test_tool_failure_fails_the_run_notifies_and_cleans_up(env):
    env["state"]["tool_rc"] = 1
    assert env["mod"].main(["check"]) == 1
    assert ("container", "removed") in env["calls"] and ("tunnel", "closed") in env["calls"]
    assert "notify" in kinds(env)


def test_a_failed_run_deletes_nothing(env):
    point(env["remote"], "20261126T031500Z")
    older = env["root"] / "prerelease-2026-11-25"
    point(older, "20261125T200141Z", verified_prerelease=True)
    env["state"]["tool_rc"] = 1
    env["mod"].main(["backup"])
    assert older.exists()


def test_drill_refuses_without_the_identity(env):
    point(env["remote"], "20261126T031500Z")
    assert env["mod"].main(["drill"]) == 1
    assert "tool" not in kinds(env)


def test_drill_restores_the_newest_point_and_deletes_the_identity(env):
    point(env["remote"], "20261125T031500Z")
    point(env["remote"], "20261126T031500Z")
    (env["root"] / "identity.txt").write_text("AGE-SECRET-KEY-FAKE\n")
    assert env["mod"].main(["drill"]) == 0
    args = [c for c in env["calls"] if c[0] == "tool"][0][1]
    assert args[0] == "restore" and args[2].endswith("cth-db-20261126T031500Z-manual.dump.age")
    assert not (env["root"] / "identity.txt").exists()


def test_another_run_holding_the_lock_means_this_check_exits(env):
    with env["mod"].run_lock(0):
        assert env["mod"].main(["check"]) == env["mod"].EX_TEMPFAIL
    assert env["calls"] == []


# --------------------------------------------------------------------------- one copy


def test_a_verified_point_on_the_drive_deletes_older_prerelease_points(env):
    point(env["remote"], "20261126T031500Z")
    older, newer, abandoned = (env["root"] / f"prerelease-{n}" for n in ("2026-11-25", "2026-11-27", "x"))
    point(older, "20261125T200141Z", verified_prerelease=True)
    point(newer, "20261127T200000Z")
    abandoned.mkdir()
    assert env["mod"].main(["check"]) == 0
    assert not older.exists() and not abandoned.exists()
    assert newer.exists()


def test_a_newer_verified_prerelease_point_deletes_the_drive_point(env):
    point(env["remote"], "20261125T031500Z")
    release = env["root"] / "prerelease-2026-11-25"
    point(release, "20261125T200141Z", verified_prerelease=True)
    assert env["mod"].main(["check"]) == 0
    assert list(env["remote"].iterdir()) == []
    assert release.exists()


def test_the_destruction_check_then_compares_against_the_prerelease_point(env):
    """Review on #1873: an identity created after the scheduled point and destroyed after the pre-release point
    went unnoticed while the check still compared against the deleted scheduled point."""
    state = env["root"] / "scheduled" / "state"
    state.mkdir()
    (state / "state.json").write_text(json.dumps({"newest_point": {"stem": "old", "identities": {"seats": []}},
                                                  "points": ["old"]}))
    point(env["remote"], "20261125T031500Z")
    point(env["root"] / "prerelease-2026-11-25", "20261125T200141Z", verified_prerelease=True)
    assert env["mod"].main(["check"]) == 0
    saved = json.loads((state / "state.json").read_text())
    assert saved["newest_point"]["identities"] == {"seats": [7]}
    assert saved["newest_point"]["off_host"] is False
    assert saved["points"] == ["old"]


def test_a_prerelease_run_in_progress_is_never_deleted(env):
    """Review on #1873: a scheduled run could delete the folder a pre-release dump was writing into."""
    point(env["remote"], "20261126T031500Z")
    running = env["root"] / "prerelease-2026-11-27"
    running.mkdir()
    import fcntl
    with open(running / "run.lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert env["mod"].main(["check"]) == 0
        assert running.exists()


def test_an_unverified_prerelease_point_deletes_nothing_on_the_drive(env):
    point(env["remote"], "20261125T031500Z")
    point(env["root"] / "prerelease-2026-11-25", "20261125T200141Z")  # no restore.ok
    assert env["mod"].main(["check"]) == 0
    assert list(env["remote"].iterdir()) != []


def test_this_computer_keeps_no_second_copy_of_the_drive_point(env):
    point(env["remote"], "20261126T031500Z")
    local = env["root"] / "scheduled" / "state" / "points"
    point(local, "20261126T031500Z")
    assert env["mod"].main(["backup"]) == 0
    assert list(local.iterdir()) == []


def test_usage():
    import subprocess, sys
    proc = subprocess.run([sys.executable, str(RUNNER), "bogus"], capture_output=True, text=True)
    assert proc.returncode == 2 and "usage" in proc.stdout


def _load():
    spec = importlib.util.spec_from_file_location("cth_backup_scheduled_real", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_folder_at_the_mount_point_is_not_the_drive(tmp_path):
    mod = _load()
    assert mod.drive_mounted("/")
    assert not mod.drive_mounted(tmp_path)


def test_a_tunnel_that_never_listens_fails_the_run(tmp_path, monkeypatch):
    mod = _load()
    stub = tmp_path / "ssh"
    stub.write_text("#!/bin/sh\nexit 255\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    with pytest.raises(RuntimeError, match="did not come up"):
        with mod.tunnel({"tunnel_port": 1, "ssh_host": "nowhere"}):
            pass


def test_a_port_already_in_use_is_never_taken_for_production(tmp_path, monkeypatch):
    """Review on #1873: with another listener on the port the run went ahead after ssh had failed."""
    import socket
    mod = _load()
    stub = tmp_path / "ssh"
    stub.write_text("#!/bin/sh\nexit 255\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    with socket.socket() as other:
        other.bind(("127.0.0.1", 0))
        other.listen()
        with pytest.raises(RuntimeError, match="already in use"):
            with mod.tunnel({"tunnel_port": other.getsockname()[1], "ssh_host": "nowhere"}):
                pass
