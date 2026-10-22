"""`infra/db-backup/prerelease.sh` closes the SSH tunnel to production that it opens.

v2.3.0 release, 2026-10-22: `backup` started `ssh -f -N -L 55433:…` and nothing ever closed it. The v2.2.4
tunnel was still listening six days later, a standing port forward to the production database on the operator's
Mac, and it made the v2.3.0 backup refuse to start. All three steps need the tunnel, so it now lives behind a
control socket: `backup` keeps it on success and closes it on failure, `counts` and `restore` reuse or reopen it,
`restore` (the last step) closes it on exit, and `close-tunnel` closes an abandoned run's.

The real script runs here against stub `ssh`, `docker`, `lsof`, `sleep`, `pg_dump`, `age-keygen` and backup tool,
in a throwaway HOME. Nothing reaches a network or a database.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "infra" / "db-backup" / "prerelease.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash unavailable")

SSH_STUB = r"""#!/bin/bash
echo "$*" >> "$STUB_LOG"
args="$*"
sock=""; prev=""
for a in "$@"; do [ "$prev" = "-S" ] && sock="$a"; prev="$a"; done
case "$args" in
  *"-O check"*) [ -f "$STUB_STATE/tunnel" ] && exit 0 || exit 255 ;;
  *"-O exit"*)  rm -f "$STUB_STATE/tunnel"; exit 0 ;;
  *" -M "*)     touch "$STUB_STATE/tunnel"
                python3 -c "import socket,sys; socket.socket(socket.AF_UNIX).bind(sys.argv[1])" "$sock"; exit 0 ;;
  *"systemctl stop"*) exit "${FAKE_APP_STAYS_ACTIVE:-0}" ;;
esac
exit 0
"""


@pytest.fixture
def env():
    # A short root: a control socket path must stay under the 104-byte UNIX socket limit on macOS.
    root = Path(tempfile.mkdtemp(prefix="cthpr", dir="/tmp"))
    home, stubs, state = root / "h", root / "bin", root / "s"
    for d in (home / "cth-backup", home / "cth-backup-venv" / "bin", stubs, state):
        d.mkdir(parents=True)
    (home / "cth-backup" / "source_url").write_text("postgresql://u:p@127.0.0.1:55433/db\n")
    (home / "cth-backup" / "recipients.txt").write_text("age1fake\n")

    def stub(name, body):
        path = stubs / name
        path.write_text(body if body.startswith("#!") else "#!/bin/bash\n" + body + "\n")
        path.chmod(0o755)

    stub("ssh", SSH_STUB)
    stub("docker", "exit 0")
    stub("sleep", "exit 0")
    stub("pg_dump", "echo 'pg_dump (PostgreSQL) 14.0'")
    stub("lsof", 'exit "${FAKE_PORT_BUSY:-1}"')
    stub("age-keygen", 'echo "${FAKE_RECIPIENT:-age1fake}"')
    tool = home / "cth-backup-venv" / "bin" / "python"
    tool.write_text('#!/bin/bash\necho "tool $*"\nexit "${FAKE_TOOL_FAILS:-0}"\n')
    tool.chmod(0o755)

    base = {
        "HOME": str(home),
        "PATH": f"{stubs}:/usr/bin:/bin:/usr/sbin:/sbin",
        "STUB_LOG": str(state / "calls.log"),
        "STUB_STATE": str(state),
    }
    yield {"root": root, "home": home, "state": state, "base": base}
    shutil.rmtree(root, ignore_errors=True)


def run(env, *args, **extra):
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env={**env["base"], **{k: str(v) for k, v in extra.items()}},
        capture_output=True, text=True, timeout=60,
    )


def tunnel_open(env):
    return (env["state"] / "tunnel").exists()


def ssh_calls(env):
    log = env["state"] / "calls.log"
    return log.read_text().splitlines() if log.exists() else []


def opened_with_control_socket(env):
    return any(" -M " in f" {c} " and "-S" in c and "-L 55433:127.0.0.1:5432" in c for c in ssh_calls(env))


def test_backup_keeps_the_tunnel_open_for_counts_and_restore(env):
    result = run(env, "backup")
    assert result.returncode == 0, result.stdout + result.stderr
    assert opened_with_control_socket(env)
    assert tunnel_open(env)


def test_backup_closes_the_tunnel_when_the_app_will_not_stop(env):
    result = run(env, "backup", FAKE_APP_STAYS_ACTIVE=1)
    assert result.returncode != 0
    assert "still active" in result.stdout
    assert not tunnel_open(env)
    assert any("-O exit" in c for c in ssh_calls(env))


def test_backup_closes_the_tunnel_when_the_backup_tool_fails(env):
    result = run(env, "backup", FAKE_TOOL_FAILS=1)
    assert result.returncode != 0
    assert not tunnel_open(env)


def test_restore_closes_the_tunnel_and_deletes_the_identity(env):
    assert run(env, "backup").returncode == 0 and tunnel_open(env)
    identity = env["home"] / "cth-backup" / "identity.txt"
    identity.write_text("AGE-SECRET-KEY-FAKE\n")

    result = run(env, "restore", CTH_BACKUP_STATE_DIR=env["home"] / "cth-backup" / "empty-run")
    # No point in that state dir: restore exits early, which must still close the tunnel and delete the identity.
    assert result.returncode != 0
    assert not tunnel_open(env)
    assert not identity.exists()


def test_restore_closes_the_tunnel_after_a_successful_restore(env):
    state_dir = env["home"] / "cth-backup" / "run"
    (state_dir / "points").mkdir(parents=True)
    assert run(env, "backup", CTH_BACKUP_STATE_DIR=state_dir).returncode == 0
    (state_dir / "points" / "cth-db-x-manual.dump.age").write_text("x")
    identity = env["home"] / "cth-backup" / "identity.txt"
    identity.write_text("AGE-SECRET-KEY-FAKE\n")

    result = run(env, "restore", CTH_BACKUP_STATE_DIR=state_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "restore --artifact" in result.stdout
    assert "tunnel closed" in result.stdout
    assert not tunnel_open(env)
    assert not identity.exists()


def test_close_tunnel_closes_an_abandoned_run(env):
    assert run(env, "backup").returncode == 0 and tunnel_open(env)
    result = run(env, "close-tunnel")
    assert result.returncode == 0
    assert not tunnel_open(env)


def test_backup_refuses_a_port_held_by_something_it_does_not_own(env):
    result = run(env, "backup", FAKE_PORT_BUSY=0)
    assert result.returncode != 0
    assert "does not own" in result.stdout
    assert not opened_with_control_socket(env)
