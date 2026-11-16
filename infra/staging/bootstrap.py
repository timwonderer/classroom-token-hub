"""Join one enrolled staging guest and invoke the reviewed B2 installer over pinned SSH."""
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
import stat
import subprocess
import sys
import time
from urllib.parse import urlsplit
from uuid import UUID

# Only the trusted coordinator checkout runs on this machine. The application bundle runs on the guest.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "self-hosting"))
from install import STAGES
import runtime as b2_runtime

SOURCE = "/root/cth-stage-source"
TRANSFER = "/root/cth-stage-input"
MANIFEST = "/etc/cth/installation.json"
CLEAN_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
HASH = re.compile("[0-9a-f]{64}")
RFC1918 = tuple(ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


class BootstrapError(Exception):
    """Only fixed failure classes may cross the coordinator boundary."""


def require(ok, code):
    if not ok:
        raise BootstrapError(code)


def json_object(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate_field")
            result[key] = value
        return result
    try:
        result = json.loads(raw, object_pairs_hook=unique)
    except (ValueError, UnicodeError):
        raise BootstrapError("invalid_json") from None
    require(isinstance(result, dict), "invalid_json")
    return result


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def public_key(key):
    require(isinstance(key, str) and re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/]{68}", key), "invalid_host_key")
    raw = base64.b64decode(key.split()[1], validate=True)
    require(len(raw) == 51 and raw.startswith(b"\0\0\0\x0bssh-ed25519\0\0\0\x20"), "invalid_host_key")
    return key


def checked_private_ip(address):
    try:
        ip = ipaddress.IPv4Address(address)
    except ValueError:
        raise BootstrapError("invalid_private_address") from None
    require(any(ip in net for net in RFC1918), "invalid_private_address")
    return str(ip)


def protected(path, directory, owner):
    st = path.lstat()
    require(path == path.resolve() and st.st_uid == owner, "untrusted_path")
    if directory:
        require(stat.S_ISDIR(st.st_mode) and not st.st_mode & 0o022, "untrusted_directory")
    else:
        require(stat.S_ISREG(st.st_mode) and not st.st_mode & 0o027 and st.st_nlink == 1
                and (not st.st_mode & 0o040 or st.st_gid == os.getegid()),
                "untrusted_file")


def capture_ssh(argv, command, timeout):
    """Keep at most a single small receipt in memory, discard all diagnostic streams."""
    deadline = time.monotonic() + timeout
    output = bytearray()
    with subprocess.Popen([*argv, command], env=CLEAN_ENV, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as p:
        try:
            while True:
                remaining = deadline - time.monotonic()
                require(remaining > 0 and select.select([p.stdout], [], [], remaining)[0], "guest_timeout")
                chunk = os.read(p.stdout.fileno(), 4096)
                if not chunk:
                    break
                output.extend(chunk)
                require(len(output) <= 4096, "oversized_guest_receipt")
            require(p.wait(timeout=max(.01, deadline - time.monotonic())) == 0, "guest_command_failed")
        finally:
            if p.poll() is None:
                p.kill()
    return bytes(output)


class Prepared:
    def __init__(self, inputs_dir, run_dir, installation_id, sha, expires):
        self.inputs = Path(inputs_dir)
        self.run_dir = Path(run_dir)
        require(self.inputs.name == self.run_dir.name and self.inputs.is_absolute() and self.run_dir.is_absolute(),
                "invalid_run_directory")
        require(str(UUID(installation_id)) == installation_id and re.fullmatch("[a-f0-9]{40}", sha),
                "invalid_run_identity")
        self.installation_id, self.sha, self.expires = installation_id, sha, expires

    def _input(self, name, limit=65536):
        protected(self.inputs, True, 0)
        path = self.inputs / name
        protected(path, False, 0)
        require(0 < path.stat().st_size <= limit, "invalid_input_size")
        return path

    def _profile(self):
        cfg = json_object(self._input("authority.json").read_bytes())
        require(set(cfg) == {"release_sha","hostname","admission_hostname","marketing_url","passwordless_url",
                             "allowed_hosts","bundle_sha256","connector_sha256","acceptance_sha256"}
                and cfg["release_sha"] == self.sha, "approval_mismatch")
        hosts = cfg["allowed_hosts"]
        require(isinstance(hosts,list) and 1 <= len(hosts) <= 8 and all(b2_runtime.hostname(h) for h in hosts)
                and cfg["hostname"] in hosts and cfg["admission_hostname"] in hosts
                and cfg["hostname"] != cfg["admission_hostname"], "invalid_endpoint_approval")
        for key in ("marketing_url", "passwordless_url"):
            url = urlsplit(cfg[key])
            require(url.scheme == "https" and url.netloc == url.hostname and url.hostname in hosts
                    and not url.query and not url.fragment, "unapproved_endpoint")
        for filename, key, limit in (("release.bundle","bundle_sha256",1024**3),
                                      ("connector","connector_sha256",256*1024**2),
                                      ("acceptance.sh","acceptance_sha256",1024**2)):
            if key == "acceptance_sha256" and cfg[key] is None:
                continue
            require(isinstance(cfg[key],str) and HASH.fullmatch(cfg[key])
                    and digest(self._input(filename, limit)) == cfg[key], "unapproved_payload")
        heads = subprocess.run(["git","bundle","list-heads",self.inputs/"release.bundle"],
                               capture_output=True, env=CLEAN_ENV, timeout=60, check=False)
        require(heads.returncode == 0 and any(line.split(b" ", 1)[0] == self.sha.encode()
                for line in heads.stdout.splitlines()), "bundle_missing_approved_head")
        if cfg["acceptance_sha256"] is not None:
            access = json_object(self._input("acceptance.json").read_bytes())
            require(set(access) == {"CF-Access-Client-Id", "CF-Access-Client-Secret"}
                    and all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_.-]{16,256}", v)
                            for v in access.values()), "invalid_acceptance_credentials")
        return cfg

    def _runtime(self, cfg):
        providers = json_object(self._input("integration.json").read_bytes())
        require(set(providers) == b2_runtime.PROVIDERS and all(isinstance(v,str) for v in providers.values()),
                "provider_credentials_missing")
        values = {k: secrets.token_hex(32) for k in b2_runtime.KEYS}
        values.update(providers, ENCRYPTION_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
                      FLASK_ENV="production", DATABASE_URL="postgresql:///cth_stage?host=/var/run/postgresql&port=5432",
                      RATELIMIT_STORAGE_URI="redis+unix://"+b2_runtime.RATE_SOCKET,
                      STUDENT_SETUP_REDIS_URL="unix://"+b2_runtime.SETUP_SOCKET, LOG_FILE="/var/log/cth-web/app.log",
                      MARKETING_SITE_URL=cfg["marketing_url"], PASSWORDLESS_API_URL=cfg["passwordless_url"])
        raw = "".join(k+"="+v+"\n" for k,v in values.items())
        try:
            require(b2_runtime.parse_env(raw, {"database":"cth_stage"}) == values, "invalid_runtime_input")
        except ValueError:
            raise BootstrapError("invalid_runtime_input") from None
        return raw.encode()

    def _bind(self, create=False):
        uid = os.geteuid()
        protected(self.run_dir.parent, True, uid)
        if create:
            self.run_dir.mkdir(mode=0o700, exist_ok=True)
        protected(self.run_dir, True, uid)
        require(stat.S_IMODE(self.run_dir.stat().st_mode) == 0o700, "untrusted_directory")
        marker = self.run_dir / "bootstrap.id"
        if create and not marker.exists():
            with marker.open("x") as f:
                os.fchmod(f.fileno(), 0o600)
                f.write(self.installation_id)
        protected(marker, False, uid)
        require(marker.read_text() == self.installation_id, "run_identity_changed")

    def cloud_init(self):
        require(time.time() < self.expires, "lease_expired")
        profile = self._profile()
        self._runtime(profile)  # Detect bad inputs before any allocation.
        for name in ("origin.crt","origin.key","tunnel.token"):
            self._input(name)
        self._bind(create=True)
        key = self.run_dir / "client"
        if not key.exists():
            subprocess.run(["ssh-keygen","-q","-t","ed25519","-C","staging","-N","","-f",str(key)],
                           check=True, env=CLEAN_ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        protected(key, False, os.geteuid())
        pub = public_key(" ".join(key.with_suffix(".pub").read_text().split()[:2]))
        # Never send application credentials or a private host key to the metadata service.
        return "#cloud-config\n"+json.dumps({
            "disable_root":False, "ssh_pwauth":False, "ssh_deletekeys":True,
            "write_files":[{"path":"/etc/cth-stage-id","permissions":"0444","content":self.installation_id},
                           {"path":"/etc/cth-stage.pub","permissions":"0444","content":"restrict "+pub+"\n"}],
            "runcmd":[["install","-d","-m","0700","/root/.ssh"],
                      ["install","-m","0600","/etc/cth-stage.pub","/root/.ssh/authorized_keys"],
                      ["sh","-ec","mkdir -p /etc/issue.d; "
                       "(echo CTH-stage-enrollment; cat /etc/cth-stage-id; echo; "
                       "cat /etc/ssh/ssh_host_ed25519_key.pub) > /etc/issue.d/50-cth-stage.issue; "
                       "cat /etc/issue.d/50-cth-stage.issue > /dev/console; agetty --reload"]]
        })

    def _ssh(self, address, droplet_id):
        self._bind()
        ip = checked_private_ip(address)
        pin = json_object(self._input("host-pin.json").read_bytes())
        require(set(pin)=={"installation_id","droplet_id","host_key"} and type(droplet_id) is int and droplet_id > 0
                and pin["installation_id"] == self.installation_id and type(pin["droplet_id"]) is int
                and pin["droplet_id"] == droplet_id, "host_pin_mismatch")
        alias = "cth-"+self.installation_id
        line = alias+" "+public_key(pin["host_key"])+"\n"
        hosts = self.run_dir/"known_hosts"
        try:
            with hosts.open("x") as f:
                os.fchmod(f.fileno(),0o600)
                f.write(line)
        except FileExistsError:
            pass
        protected(hosts,False,os.geteuid())
        require(hosts.read_text() == line,"host_pin_changed")
        key = self.run_dir/"client"
        protected(key,False,os.geteuid())
        return ["ssh","-F","/dev/null","-T","-q","-i",str(key),"-o","IdentitiesOnly=yes","-o","IdentityAgent=none",
                "-o","PreferredAuthentications=publickey","-o","BatchMode=yes","-o","StrictHostKeyChecking=yes",
                "-o","GlobalKnownHostsFile=/dev/null","-o","HostKeyAlgorithms=ssh-ed25519","-o","UpdateHostKeys=no",
                "-o","UserKnownHostsFile="+str(hosts),"-o","HostKeyAlias="+alias,"-o","ConnectTimeout=5",
                "-o","ForwardAgent=no","-o","ClearAllForwardings=yes","root@"+ip]

    def _identity(self, address, droplet_id):
        argv = self._ssh(address,droplet_id)
        result = capture_ssh(argv,
            "set -eu; cat /etc/cth-stage-id; echo; curl -qfsS --noproxy '*' --max-time 4 "
            "http://169.254.169.254/metadata/v1/id; echo; cat /etc/machine-id",10).split()
        require(len(result)==3 and result[:2]==[self.installation_id.encode(), str(droplet_id).encode()]
                and re.fullmatch(b"[0-9a-f]{32}",result[2]) and result[2]!=b"0"*32,"guest_identity_mismatch")
        return argv,result[2].decode()

    def prove(self, address, droplet_id):
        try:
            self._identity(address,droplet_id)
            return True
        except (BootstrapError, OSError, ValueError, subprocess.SubprocessError):
            return False

    def _remaining(self, cap):
        seconds = min(self.expires - time.time(), cap)
        require(seconds > 0, "lease_expired")
        return seconds

    def _run(self, argv, cmd, data=None, cap=600):
        kw = {"stdin": subprocess.DEVNULL} if data is None else (
            {"input":data} if isinstance(data,bytes) else {"stdin":data})
        result = subprocess.run([*argv,cmd],env=CLEAN_ENV,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                timeout=self._remaining(cap),**kw)
        require(result.returncode == 0, "guest_command_failed")

    def _upload(self, argv, dest, data):
        # dest is always an absolute path selected by this adapter.
        cmd = "umask 077; set -C; cat > "+shlex.quote(dest)
        if isinstance(data,Path):
            with data.open("rb") as f:
                self._run(argv,cmd,f)
        else:
            self._run(argv,cmd,data)

    def install(self, address, droplet_id, record):
        # Console enrollment is an independent operator/provider trust channel.
        deadline = time.monotonic()+self._remaining(600)
        while not self.prove(address,droplet_id):
            require(time.monotonic()<deadline,"host_join_timeout")
            time.sleep(3)
        argv,machine_id = self._identity(address,droplet_id)
        cfg = self._profile()
        env = self._runtime(cfg)
        manifest = {"installation_id":self.installation_id,"machine_id":machine_id,"release_sha":self.sha,
                    "database":"cth_stage","hostname":cfg["hostname"],"runtime_env":"/etc/cth/runtime.env",
                    "admission_hostname":cfg["admission_hostname"], "tls_cert":"/etc/cth/origin.crt",
                    "tls_key":"/etc/cth/origin.key"}
        self._run(argv,"set -eu; cloud-init status --wait >/dev/null; umask 077; "
                  "mkdir "+TRANSFER+" /etc/cth; test ! -e "+SOURCE+"; "
                  "command -v git >/dev/null || (apt-get update && apt-get -y install --no-install-recommends git)")
        for dest, data in ((TRANSFER+"/release.bundle",self.inputs/"release.bundle"),
                           (TRANSFER+"/connector",self.inputs/"connector"),
                           (TRANSFER+"/tunnel.token",self._input("tunnel.token")),
                           (manifest["tls_cert"],self._input("origin.crt")),(manifest["tls_key"],self._input("origin.key")),
                           (manifest["runtime_env"],env),(MANIFEST,json.dumps(manifest).encode())):
            self._upload(argv,dest,data)
        self._run(argv,"set -eu; cd "+TRANSFER+"; echo '"+cfg["bundle_sha256"]+"  release.bundle' | sha256sum -c -; "
                  "echo '"+cfg["connector_sha256"]+"  connector' | sha256sum -c -; "
                  "git clone --no-checkout release.bundle "+SOURCE+"; cd "+SOURCE+"; git checkout --detach "+self.sha+
                  '; test "$(git rev-parse HEAD)" = '+self.sha)
        for stage in STAGES:
            if stage == "ingress":
                # Existing protected tunnel enrollment is independent of application execution.
                cmd = ("set -eu; chmod 0700 "+TRANSFER+"/connector; systemd-run --unit=cth-stage-tunnel "
                       "-p NoNewPrivileges=yes -p ProtectSystem=strict -p StandardOutput=null -p StandardError=null "
                       +TRANSFER+"/connector tunnel --no-autoupdate run --token-file "+TRANSFER+"/tunnel.token")
                self._run(argv,cmd)
            for action in ("apply","check"):
                receipt = capture_ssh(argv,"cd "+SOURCE+" && python3 infra/self-hosting/install.py "+
                                      action+" "+stage+" --config "+MANIFEST,self._remaining(1200))
                require(json_object(receipt)=={"installation_id":self.installation_id,"release_sha":self.sha,
                                               "stage":stage,"action":action,"result":"ok"}, "invalid_stage_receipt")
            record(stage,"ok")
        if cfg["acceptance_sha256"]:
            dest = "/opt/cth/staging-acceptance.sh"
            self._upload(argv,dest,self._input("acceptance.sh",1024**2))
            self._upload(argv,TRANSFER+"/acceptance.json",self._input("acceptance.json"))
            self._run(argv, "set -eu; echo '"+cfg["acceptance_sha256"]+"  "+dest+"' | sha256sum -c -; "
                      "chmod 0555 "+dest+"; exec systemd-run --wait --collect --unit=cth-stage-acceptance "
                      "-p DynamicUser=yes -p NoNewPrivileges=yes -p PrivateTmp=yes -p ProtectSystem=strict "
                      "-p ProtectHome=yes -p StandardOutput=null -p StandardError=null "
                      "-p RuntimeDirectory=cth-stage-acceptance -p RuntimeDirectoryMode=0700 "
                      "-p WorkingDirectory=/run/cth-stage-acceptance -p Environment=HOME=/run/cth-stage-acceptance "
                      "-p LoadCredential=admission.json:"+TRANSFER+"/acceptance.json "
                      "-p Environment=PATH=/opt/cth/venvs/"+self.sha+"/bin:/usr/bin:/bin "
                      "-p Environment=CTH_PUBLIC_ORIGIN=https://"+manifest["hostname"]+" /bin/sh "+dest)
            record("acceptance","ok")

    def revoked(self,droplet_id):
        try:
            receipt = json_object(self._input("revoked.json").read_bytes())
            return (receipt == {"installation_id":self.installation_id,"droplet_id":droplet_id,"integrations_revoked":True}
                    and receipt["integrations_revoked"] is True and type(receipt["droplet_id"]) is type(droplet_id))
        except (BootstrapError, OSError, ValueError):
            return False

    def cleanup(self):
        if not self.run_dir.exists():
            return
        if not (self.run_dir/"bootstrap.id").exists():
            require(not any(self.run_dir.iterdir()), "unrecognized_bootstrap_state")
            return
        self._bind()
        for name in ("client","client.pub","known_hosts","bootstrap.id"):
            (self.run_dir/name).unlink(missing_ok=True)
