"""Install the approved application SHA on one attended, console-pinned staging Droplet."""

import argparse
import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import select
import shlex
import shutil
import subprocess
import sys
import time
from uuid import UUID

# Import only from the trusted controller checkout. The target application's code runs on the Droplet.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "self-hosting"))
from install import STAGES
import runtime

SOURCE = "/root/cth-source"
INPUTS = "/root/cth-stage"
MANIFEST = "/etc/cth/installation.json"
CLEAN = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}


def require(ok):
    if not ok:
        raise ValueError("staging precondition failed")


def cloud_init(installation_id):
    """Expose the fresh guest's public pin in the authenticated recovery console before login."""
    require(str(UUID(installation_id)) == installation_id)
    return "#cloud-config\n" + json.dumps(
        {
            "disable_root": False,
            "ssh_pwauth": False,
            "ssh_deletekeys": True,
            "write_files": [
                {"path": "/etc/cth-stage-id", "permissions": "0444", "content": installation_id + "\n"}
            ],
            "runcmd": [
                [
                    "sh",
                    "-ec",
                    "mkdir -p /etc/issue.d; (echo CTH-staging; cat /etc/cth-stage-id; "
                    "cat /etc/ssh/ssh_host_ed25519_key.pub) > /etc/issue.d/50-cth-stage.issue; "
                    "cat /etc/issue.d/50-cth-stage.issue > /dev/console; agetty --reload",
                ]
            ],
        }
    )


def host_pin(raw, number, installation_id):
    pin = json.loads(raw)
    require(
        set(pin) == {"installation_id", "droplet_id", "host_key"}
        and type(pin["droplet_id"]) is int
        and pin["droplet_id"] == number
        and pin["installation_id"] == installation_id
    )
    key = pin["host_key"]
    require(
        re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/]{68}", key)
        and base64.b64decode(key.split()[1]).startswith(b"\0\0\0\x0bssh-ed25519\0\0\0\x20")
    )
    return key


def checked_runtime(args, machine_id, env):
    cfg = {
        "installation_id": args.installation_id,
        "machine_id": machine_id,
        "release_sha": args.sha,
        "database": "cth_stage",
        "hostname": env["STAGING_HOSTNAME"],
        "admission_hostname": env["STAGING_ADMISSION_HOSTNAME"],
        "runtime_env": "/etc/cth/runtime.env",
        "tls_cert": "/etc/cth/origin.crt",
        "tls_key": "/etc/cth/origin.key",
    }
    # Omitted for the default so older release installers still accept the manifest.
    if args.python != "3.10":
        cfg["python"] = args.python
    runtime.validate_config(cfg)
    values = {k: secrets.token_hex(32) for k in runtime.KEYS}
    values.update({k: env["STAGING_" + k] for k in runtime.PROVIDERS})
    values.update(
        ENCRYPTION_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        FLASK_ENV="production",
        PASSKEY_EXPECTED_ORIGIN="https://" + cfg["hostname"],
        DATABASE_URL="postgresql:///cth_stage?host=/var/run/postgresql&port=5432",
        RATELIMIT_STORAGE_URI="redis+unix://" + runtime.RATE_SOCKET,
        STUDENT_SETUP_REDIS_URL="unix://" + runtime.SETUP_SOCKET,
        LOG_FILE="/var/log/cth-web/app.log",
    )
    for setting, variable in (("STAGING_MARKETING_URL", "MARKETING_SITE_URL"),
                              ("STAGING_PASSWORDLESS_URL", "PASSWORDLESS_API_URL")):
        if env.get(setting):
            values[variable] = env[setting]
    raw = "".join(k + "=" + v + "\n" for k, v in values.items())
    require(runtime.parse_env(raw, cfg) == values)
    return cfg, raw.encode()


class Guest:
    def __init__(self, args, work, env):
        require(
            str(UUID(args.installation_id)) == args.installation_id
            and args.droplet_id > 0
            and re.fullmatch("[0-9a-f]{40}", args.sha)
        )
        address = ipaddress.IPv4Address(args.address)
        require(address.is_global and not address.is_multicast and not address.is_reserved)
        key = host_pin(env["STAGING_HOST_PIN"], args.droplet_id, args.installation_id)
        identity = work / "identity"
        identity.write_text(env["STAGING_SSH_PRIVATE_KEY"].rstrip() + "\n")
        identity.chmod(0o600)
        known = work / "known_hosts"
        known.write_text(str(address) + " " + key + "\n")
        self.ssh = [
            "ssh",
            "-q",
            "-T",
            "-F",
            "/dev/null",
            "-i",
            str(identity),
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "IdentityAgent=none",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "UserKnownHostsFile=" + str(known),
            "-o",
            "GlobalKnownHostsFile=/dev/null",
            "-o",
            "HostKeyAlgorithms=ssh-ed25519",
            "-o",
            "UpdateHostKeys=no",
            "-o",
            "ConnectTimeout=8",
            "-o",
            "ClearAllForwardings=yes",
            "-o",
            "ForwardAgent=no",
            "root@" + str(address),
        ]

    def run(self, cmd, data=None):
        kwargs = (
            {"stdin": subprocess.DEVNULL}
            if data is None
            else ({"input": data} if isinstance(data, bytes) else {"stdin": data})
        )
        subprocess.run(
            [*self.ssh, cmd],
            check=True,
            env=CLEAN,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1200,
            **kwargs,
        )

    def receipt(self, cmd):
        deadline = time.monotonic() + 1200
        with subprocess.Popen(
            [*self.ssh, cmd],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=CLEAN,
        ) as process:
            output = bytearray()
            try:
                while True:
                    wait = deadline - time.monotonic()
                    require(wait > 0 and select.select([process.stdout], [], [], wait)[0])
                    chunk = os.read(process.stdout.fileno(), 4096)
                    if not chunk:
                        break
                    output.extend(chunk)
                    require(len(output) <= 4096)
                require(process.wait(timeout=max(0.01, deadline - time.monotonic())) == 0)
            finally:
                if process.poll() is None:
                    process.kill()
        return bytes(output)

    def upload(self, destination, data):
        command = "set -C; umask 077; cat > " + shlex.quote(destination)
        if isinstance(data, Path):
            with data.open("rb") as stream:
                self.run(command, stream)
        else:
            self.run(command, data)


def local(argv, timeout=120):
    return subprocess.check_output(
        argv, env=CLEAN, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout
    )


def install(args, work, env, record):
    guest = Guest(args, work, env)
    facts = guest.receipt(
        "set -eu; cloud-init status --wait >/dev/null; cat /etc/cth-stage-id; "
        "curl -qfsS --noproxy '*' --max-time 5 http://169.254.169.254/metadata/v1/id; echo; cat /etc/machine-id"
    ).split()
    require(
        len(facts) == 3
        and facts[:2] == [args.installation_id.encode(), str(args.droplet_id).encode()]
        and re.fullmatch(b"[0-9a-f]{32}", facts[2])
        and facts[2] != b"0" * 32
    )
    cfg, raw = checked_runtime(args, facts[2].decode(), env)
    root = args.release.resolve()
    git = ["git", "-C", str(root)]
    require(
        local([*git, "rev-parse", "HEAD"]).strip().decode() == args.sha
        and local([*git, "rev-parse", "--is-shallow-repository"]).strip() == b"false"
    )
    bundle = work / "release.bundle"
    local([*git, "bundle", "create", str(bundle), "HEAD"])
    hook = None
    if args.acceptance_script or args.acceptance_sha256:
        require(
            args.acceptance_script
            and re.fullmatch("[a-f0-9]{64}", args.acceptance_sha256)
            and re.fullmatch(r"[A-Za-z0-9_./-]+\.sh", args.acceptance_script)
        )
        path = root / args.acceptance_script
        require(
            path.resolve() == path
            and path.is_relative_to(root)
            and path.is_file()
            and path.stat().st_size <= 1024**2
        )
        hook = local([*git, "show", args.sha + ":" + args.acceptance_script])
        require(hashlib.sha256(hook).hexdigest() == args.acceptance_sha256)
        access = {
            "CF-Access-Client-Id": env["STAGING_ACCESS_CLIENT_ID"],
            "CF-Access-Client-Secret": env["STAGING_ACCESS_CLIENT_SECRET"],
        }
        require(all(re.fullmatch(r"[a-zA-Z0-9_.-]{16,256}", v) for v in access.values()))
    for name in ("STAGING_ORIGIN_CERT", "STAGING_ORIGIN_KEY"):
        require(0 < len(env[name].strip()) <= 65536)
    guest.run(
        "set -eu; umask 077; mkdir "
        + INPUTS
        + " /etc/cth; test ! -e "
        + SOURCE
        + "; command -v git >/dev/null || (apt-get update && apt-get install -y --no-install-recommends git)"
    )
    for dest, data in (
        (INPUTS + "/release.bundle", bundle),
        (cfg["tls_cert"], env["STAGING_ORIGIN_CERT"].encode()),
        (cfg["tls_key"], env["STAGING_ORIGIN_KEY"].encode()),
        (MANIFEST, json.dumps(cfg).encode()),
        (cfg["runtime_env"], raw),
    ):
        guest.upload(dest, data)
    guest.run(
        "set -eu; cd " + INPUTS + "; "
        "git clone --no-checkout release.bundle "
        + SOURCE
        + "; cd "
        + SOURCE
        + "; git checkout --detach "
        + args.sha
        + '; test "$(git rev-parse HEAD)" = '
        + args.sha
    )
    for stage in STAGES:
        for action in ("apply", "check"):
            result = json.loads(
                guest.receipt(
                    "cd "
                    + SOURCE
                    + " && python3 infra/self-hosting/install.py "
                    + action
                    + " "
                    + stage
                    + " --config "
                    + MANIFEST
                )
            )
            require(
                result
                == {
                    "installation_id": args.installation_id,
                    "release_sha": args.sha,
                    "stage": stage,
                    "action": action,
                    "result": "ok",
                }
            )
        record(stage)
    if hook is not None:
        dest = "/opt/cth/stage-acceptance.sh"
        guest.upload(dest, hook)
        guest.upload(INPUTS + "/access.json", json.dumps(access).encode())
        guest.run(
            "set -eu; chmod 0555 " + dest + "; systemd-run --wait --collect --unit=cth-acceptance "
            "-p DynamicUser=yes -p ProtectSystem=strict -p NoNewPrivileges=yes -p PrivateTmp=yes "
            "-p StandardOutput=null -p StandardError=null -p RuntimeDirectory=cth-acceptance "
            "-p WorkingDirectory=/run/cth-acceptance -p Environment=HOME=/run/cth-acceptance "
            "-p LoadCredential=access.json:"
            + INPUTS
            + "/access.json -p Environment=CTH_PUBLIC_ORIGIN=https://"
            + cfg["hostname"]
            + " -p Environment=PATH=/opt/cth/venvs/"
            + args.sha
            + "/bin:/usr/bin:/bin /bin/sh "
            + dest
        )
        record("acceptance")


def record_stage(stage):
    require(stage in (*STAGES, "acceptance"))
    print(json.dumps({"stage": stage, "result": "ok"}), flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as summary:
            summary.write(f"- Verified `{stage}`\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--installation-id", required=True)
    parser.add_argument("--droplet-id", required=True, type=int)
    parser.add_argument("--address", required=True)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--acceptance-script", default="")
    parser.add_argument("--acceptance-sha256", default="")
    parser.add_argument("--python", choices=("3.10", "3.14"), default="3.10")
    args = parser.parse_args()
    try:
        # The GitHub-hosted job discards its runner. Also remove private files on ordinary failure.
        args.work_dir.mkdir(mode=0o700)
        try:
            install(args, args.work_dir, os.environ, record_stage)
        finally:
            shutil.rmtree(args.work_dir)
    except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError):
        sys.exit("staging bootstrap failed")


if __name__ == "__main__":
    main()
