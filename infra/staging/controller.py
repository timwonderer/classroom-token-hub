"""Restricted staging dispatch and independent cleanup on the operator coordinator."""
import contextlib
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path("/etc/cth-staging")
STATE = Path("/var/lib/cth-staging")
PROFILE = "sfo3-premium-amd"
SHA = r"[0-9a-f]{40}"
RUN = r"[1-9][0-9]{0,19}"


def require(condition):
    if not condition:
        raise ValueError("staging precondition failed")


def operator_file(path):
    for parent in path.parents:
        info = parent.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
            and not info.st_mode & 0o027 and info.st_size <= 16384)
    return path.read_text()


def parse_request(original):
    match = re.fullmatch(rf"dispatch ({RUN}) ({SHA}) ({PROFILE}) ({SHA})", original)
    require(match is not None)
    return match.groups()


def approve(request, approval, controller_sha, now):
    run_id, sha, profile, workflow_sha = request
    expected = dict(run_id=run_id, sha=sha, profile=profile, workflow_sha=workflow_sha,
                    controller_sha=controller_sha)
    require(set(approval) == set(expected) | {"dispatch_before"})
    require(all(approval[k] == v for k, v in expected.items()))
    require(type(approval["dispatch_before"]) is int and now < approval["dispatch_before"] <= now + 900)


def private_address(droplet):
    addresses = [a["ip_address"] for a in droplet["networks"]["v4"] if a["type"] == "private"]
    require(len(addresses) == 1 and ipaddress.IPv4Address(addresses[0]).is_private)
    return addresses[0]


def prepared(row):
    from bootstrap import Prepared
    run_id = row["run_id"]
    require(re.fullmatch(RUN, run_id))
    return Prepared(CONFIG / "runs" / run_id, STATE / "runs" / run_id, row["installation_id"],
                    row["sha"], row["expires_at"])


def prove(row, droplet):
    return prepared(row).prove(private_address(droplet), droplet["id"])


def retire(lifecycle, run_id, state, prepare):
    """Keep the receipt obligation independently of the provider deletion transaction."""
    with (state / "retirement.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        row = lifecycle.current(run_id)
        require(row["state"] == "closed")
        obligation = state / "pending" / run_id
        if not obligation.exists():
            return
        host = prepare(row)
        require(host.revoked(row["droplet_id"]))
        host.cleanup()
        obligation.unlink()


def mark_pending(path):
    with path.open("xb") as f:
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextlib.contextmanager
def deadline(expires_at):
    remaining = expires_at - int(time.time()) - 300
    require(remaining > 0)

    def abort(signum, frame):
        raise TimeoutError("staging deadline")

    previous = signal.signal(signal.SIGALRM, abort)
    signal.alarm(remaining)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def save_evidence(state, evidence):
    path = state / "evidence" / (evidence["run_id"] + ".json")
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as f:
        json.dump(evidence, f, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
    os.replace(f.name, path)


def execute(request, lifecycle, state, prepare, ssh_key_id, stages, *, receipt_wait=0):
    run_id, sha, profile, _ = request
    require(not any((state / "pending").iterdir()))
    row = lifecycle.reserve(run_id, sha, profile)
    evidence = {"run_id": run_id, "sha": sha, "profile": profile, "stages": [], "acceptance": "unexecuted",
                "execution": "failed", "cleanup": "unresolved", "phase": "preparation",
                "issued_at": row["issued_at"], "stage_times": []}
    save_evidence(state, evidence)

    def record(stage, outcome):
        require(outcome == "ok")
        if stage == "acceptance":
            require(evidence["stages"] == list(stages) and evidence["acceptance"] == "unexecuted")
            evidence["acceptance"] = "passed"
        else:
            index = len(evidence["stages"])
            require(index < len(stages) and stage == stages[index])
            evidence["stages"].append(stage)
            evidence["stage_times"].append(int(time.time()))
        save_evidence(state, evidence)

    try:
        with deadline(row["expires_at"]):
            # Reservation serializes cloud leases. Recheck local obligations after acquiring it.
            require(not any((state / "pending").iterdir()))
            mark_pending(state / "pending" / run_id)
            host = prepare(row)
            user_data = host.cloud_init()
            evidence["phase"] = "allocation"
            save_evidence(state, evidence)
            droplet = lifecycle.allocate(run_id, user_data=user_data, ssh_keys=[ssh_key_id])
            evidence["phase"] = "bootstrap"
            save_evidence(state, evidence)
            host.install(private_address(droplet), droplet["id"], record)
            require(evidence["stages"] == list(stages))
            evidence["execution"] = "passed"
            evidence["phase"] = "completed"
    except (Exception, KeyboardInterrupt):
        pass  # Failure text may carry provider data or enrollment material.
    finally:
        try:
            lifecycle.cleanup(run_id)
            evidence["cleanup"] = "retirement_pending"
            save_evidence(state, evidence)
            # The Droplet is already gone. Allow the operator time to retire external enrollments.
            end = time.monotonic() + receipt_wait
            while time.monotonic() < end and (state / "pending" / run_id).exists():
                closed = lifecycle.current(run_id)
                if prepare(closed).revoked(closed["droplet_id"]):
                    break
                time.sleep(min(5, max(0, end - time.monotonic())))
            retire(lifecycle, run_id, state, prepare)
            evidence["cleanup"] = "verified"
        except Exception:
            pass
    save_evidence(state, evidence)
    return evidence


def sweep(lifecycle, state, prepare):
    results = lifecycle.sweep()
    unresolved = any(r["state"] != "closed" for r in results)
    for marker in sorted((state / "pending").iterdir()):
        run_id = marker.name
        require(re.fullmatch(RUN, run_id))
        row = lifecycle.current(run_id)
        if row["state"] == "closed":
            try:
                retire(lifecycle, run_id, state, prepare)
            except Exception:
                unresolved = True
                print("run", run_id, "external retirement unresolved", file=sys.stderr)
        elif row["state"] == "unresolved" or int(time.time()) >= row["expires_at"] - 300:
            unresolved = True
            print("run", run_id, "provider reconciliation unresolved", file=sys.stderr)
    # A canceled runner might never reach artifact collection.
    for path in (state / "evidence").iterdir():
        if path.stat().st_mtime < time.time() - 3 * 86400:
            path.unlink()
    if unresolved:
        raise ValueError("cleanup unresolved")
    (state / "sweep-ok").touch(mode=0o600)


def main(argv):
    # Only the forced-command entry reads SSH_ORIGINAL_COMMAND. It never evaluates shell text.
    inspect = len(argv) == 2 and argv[0] == "inspect" and re.fullmatch(RUN, argv[1])
    require(inspect or argv in (["forced"], ["sweep"]))
    request = parse_request(os.environ.get("SSH_ORIGINAL_COMMAND", "")) if argv == ["forced"] else None
    os.umask(0o077)
    os.environ.clear()
    os.environ.update(PATH="/usr/bin:/bin", HOME="/var/empty", LC_ALL="C")
    # The dispatch account can update the ledger, never the controller or its parents.
    for directory in (ROOT, *ROOT.parents, ROOT / "infra", ROOT / "infra/staging", ROOT / "infra/self-hosting"):
        info = directory.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022)
    settings = json.loads(operator_file(CONFIG / "policy.json"))
    require(set(settings) == {"controller_sha", "provider"} and re.fullmatch(SHA, settings["controller_sha"]))
    for args, expected in ((["rev-parse", "HEAD"], settings["controller_sha"]),
                           (["status", "--porcelain", "--untracked-files=all"], "")):
        result = subprocess.run(["git", "-c", f"safe.directory={ROOT}", "-C", ROOT, *args], check=True, capture_output=True, text=True)
        require(result.stdout.strip() == expected)
    if request:
        approval_path = CONFIG / "runs" / request[0] / "approval.json"
        enrollment_deadline = time.monotonic() + 300
        while True:
            try:
                approval = json.loads(operator_file(approval_path))
                break
            except FileNotFoundError:
                require(time.monotonic() < enrollment_deadline)
                time.sleep(2)
        approve(request, approval, settings["controller_sha"], int(time.time()))
        require(0 <= time.time() - (STATE / "sweep-ok").stat().st_mtime <= 120)
    for directory in (STATE, STATE / "pending", STATE / "runs", STATE / "evidence"):
        info = directory.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077)
    from digitalocean import DigitalOcean
    from lifecycle import Lifecycle
    token = operator_file(CONFIG / "token").strip()
    provider = DigitalOcean(token, settings["provider"])
    lifecycle = Lifecycle(STATE / "inventory.sqlite", provider, prove=prove)
    if inspect:
        row = lifecycle.current(argv[1])
        fields = ("run_id", "sha", "installation_id", "issued_at", "expires_at", "state", "droplet_id", "candidates",
                  "ownership", "delete_intent", "create_rejected")
        report = {key: row[key] for key in fields}
        report["reason"] = row.get("reason")
        report["ancillary"] = row.get("ancillary")
        report["retirement_pending"] = (STATE / "pending" / argv[1]).exists()
        report["current_cleanup"] = ("unresolved" if row["state"] != "closed" else
                                     "retirement_pending" if report["retirement_pending"] else "verified")
        evidence = STATE / "evidence" / (argv[1] + ".json")
        if evidence.is_file():
            report["evidence"] = json.loads(evidence.read_bytes())
        print(json.dumps(report))
        return 0
    if request:
        # Read the canonical operator stage list from the same pinned checkout.
        sys.path.insert(0, str(ROOT / "infra" / "self-hosting"))
        from install import STAGES
        evidence = execute(request, lifecycle, STATE, prepared, settings["provider"]["ssh_key_id"], STAGES, receipt_wait=90)
        print(json.dumps(evidence, separators=(",", ":")), flush=True)
        return int(evidence["execution"] != "passed" or evidence["cleanup"] != "verified")
    sweep(lifecycle, STATE, prepared)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (Exception, KeyboardInterrupt):
        sys.exit("Staging command refused or incomplete; operator reconciliation required.")
