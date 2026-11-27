"""Reference-host runtime stages. The owning installer validates host enrollment first."""
import base64
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import time
from urllib.parse import urlsplit


TEMPLATES = Path(__file__).with_name("templates")
UNIT_DIR = Path("/etc/systemd/system")
SETUP_SOCKET = "/run/cth-student-setup/redis.sock"
RATE_SOCKET = "/run/cth-rate-limit/redis.sock"
# Explicitly disallow the project's hosted deployment as an installation destination.
HOSTED_ZONE = "classroomtokenhub.com"
KEYS = {"SECRET_KEY", "AUDIT_HMAC_KEY", "ENCRYPTION_KEY", "PEPPER_KEY", "CONFIGURATION_EXPORT_KEY"}
PROVIDERS = {"TURNSTILE_SITE_KEY", "TURNSTILE_SECRET_KEY", "PASSWORDLESS_API_PUBLIC", "PASSWORDLESS_API_KEY"}
URLS = {"MARKETING_SITE_URL", "EXTERNAL_DOCS_BASE_URL", "PASSWORDLESS_API_URL"}
INFORMATION_URLS = {"EXTERNAL_DOCS_BASE_URL", "MARKETING_SITE_URL"}
# The deployment origin is derived from the manifest hostname and set by the installer-managed
# web unit; a runtime file may carry it, but only with that exact derived value.
DERIVED_ORIGIN = "PASSKEY_EXPECTED_ORIGIN"
OPTIONAL = URLS | {DERIVED_ORIGIN}
REQUIRED = KEYS | PROVIDERS | (URLS - OPTIONAL) | {"FLASK_ENV", "DATABASE_URL", "STUDENT_SETUP_REDIS_URL",
                                      "RATELIMIT_STORAGE_URI", "LOG_FILE"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def hostname(name, informational=False):
    return (isinstance(name, str) and (informational or (name != HOSTED_ZONE and not name.endswith("." + HOSTED_ZONE)))
            and len(name) <= 253 and "." in name and all(
        re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in name.split(".")
    ) and not name.rsplit(".", 1)[1].isdigit())


# Reviewed Cloudflare IPv4 origin peers (https://www.cloudflare.com/ips-v4).
# This profile publishes an A record and listens on IPv4 only.
EDGE_IPV4 = (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
)


def validate_config(cfg):
    require(cfg.get("ingress_mode", "cloudflare-proxy") == "cloudflare-proxy", "invalid ingress mode")
    app_host = cfg.get("hostname")
    require(app_host == "staging." + HOSTED_ZONE or hostname(app_host), "invalid deployment DNS field: hostname")
    if "admission_hostname" in cfg:
        require(hostname(cfg["admission_hostname"]), "invalid deployment DNS field: admission_hostname")
        require(cfg["hostname"] != cfg["admission_hostname"], "public hostname and admission hostname must differ")
    paths = [cfg.get(key) for key in ("runtime_env", "tls_cert", "tls_key")]
    for path in paths:
        require(isinstance(path, str) and re.fullmatch(r"/etc/cth/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_.-]+", path)
                and Path(path).name not in ("", ".", "..") and not path.startswith("/etc/cth/ingress.conf"),
                "select a dedicated file under /etc/cth for runtime environment, certificate and key")
    require(len(set(paths)) == len(paths), "runtime and TLS inputs must use separate files")


def trusted_parents(path):
    for parent in reversed(path.parents):
        s = parent.lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
                "configuration directory is not root-controlled: " + str(parent))


def trusted(path, secret=False):
    path = Path(path)
    trusted_parents(path)
    s = path.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1 and
            not s.st_mode & (0o077 if secret else 0o022), "unsafe file ownership or mode: " + str(path))


def parse_env(raw, cfg):
    """Use the common literal subset of systemd EnvironmentFile syntax."""
    values = {}
    for line in raw.splitlines():
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=([A-Za-z0-9_./:@+?=,&%~-]+)", line)
        require(match is not None, "invalid EnvironmentFile syntax; values must be unquoted literals")
        key, value = match.groups()
        require(key in (REQUIRED | OPTIONAL) and key not in values, "unknown or duplicate runtime variable")
        values[key] = value
    missing = REQUIRED - values.keys()
    require(not missing, "missing runtime fields: " + ", ".join(sorted(missing)))
    expected = {"FLASK_ENV": "production", "DATABASE_URL": f"postgresql:///{cfg['database']}?host=/var/run/postgresql&port=5432",
                "STUDENT_SETUP_REDIS_URL": "unix://" + SETUP_SOCKET, "RATELIMIT_STORAGE_URI": "redis+unix://" + RATE_SOCKET,
                "LOG_FILE": "/var/log/cth-web/app.log"}
    for key, wanted in expected.items():
        require(values[key] == wanted, "incorrect reference binding for " + key)
    require(values.get(DERIVED_ORIGIN, f"https://{cfg['hostname']}") == f"https://{cfg['hostname']}",
            "incorrect reference binding for " + DERIVED_ORIGIN)
    for key in KEYS - {"ENCRYPTION_KEY"}:
        require(re.fullmatch(r"[0-9a-f]{64}", values[key]), "generate a fresh 32-byte hexadecimal value for " + key)
    enc = values["ENCRYPTION_KEY"]
    require(re.fullmatch(r"[A-Za-z0-9_-]{43}=", enc) and base64.urlsafe_b64encode(
        base64.urlsafe_b64decode(enc)).decode() == enc, "invalid Fernet ENCRYPTION_KEY")
    require(len({values[k] for k in KEYS | PROVIDERS}) == len(KEYS | PROVIDERS), "keys must be independent")
    for key in URLS & values.keys():
        u = urlsplit(values[key])
        require(u.scheme == "https" and hostname(u.hostname, informational=key in INFORMATION_URLS) and u.netloc == u.hostname and
                not u.query and not u.fragment, "select an explicit HTTPS deployment endpoint for " + key)
    # Published Turnstile test credentials bypass a real admission check.
    for key in PROVIDERS:
        require(len(values[key]) >= 12 and not re.search(r"example|placeholder|replace.me", values[key], re.I)
                and not re.match(r"^[123]x0{8,}", values[key]), "provide registered deployment credentials for " + key)
    return values


def command(*args, ok=(0,)):
    # No inherited proxy variables, libpq defaults, curl config or environment credentials.
    result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"}, timeout=90, cwd="/")
    require(result.returncode in ok, "runtime check failed (" + Path(str(args[0])).name + ")")
    return result.stdout.decode().strip()


def template(name, cfg):
    data = (TEMPLATES / name).read_text()
    if name == "ingress.conf":
        listener = "0.0.0.0:443"
        edge_address = "$realip_remote_addr"
        # Classify the TCP peer, never the visitor-controlled forwarded address.
        policy = "\n".join([
            *(f"    set_real_ip_from {net};" for net in EDGE_IPV4),
            "    geo $realip_remote_addr $peer {", "        default other;", "        127.0.0.1 local;",
            *(f"        {net} edge;" for net in EDGE_IPV4), "    }",
            '    map "$peer:$uri" $allowed {', "        default 0;", "        ~^edge: 1;",
            "        local:/health 1;", "        local:/health/status 1;", "    }",
        ])
        checks = ('        if ($allowed = 0) { return 403; }\n'
                  '        if ($ssl_server_name != "@HOST@") { return 444; }\n')
        data = data.replace("@EDGE_ADDRESS@", edge_address)
        data = data.replace("@LISTENER@", listener).replace("@PEER_POLICY@", policy).replace("@ORIGIN_CHECKS@", checks)
    for marker, key in (("INSTALL_ID", "installation_id"), ("SHA", "release_sha"), ("ENVFILE", "runtime_env"),
                        ("HOST", "hostname"), ("CERT", "tls_cert"), ("KEY", "tls_key")):
        data = data.replace("@" + marker + "@", cfg[key])
    return data.encode()


def managed(path, name, cfg, apply):
    expected = template(name, cfg)
    trusted_parents(path)
    if not os.path.lexists(path) and apply:
        # Publish complete content atomically without replacing any existing path.
        with tempfile.NamedTemporaryFile(dir=path.parent) as out:
            out.write(expected)
            out.flush()
            os.fsync(out.fileno())
            os.fchmod(out.fileno(), 0o644)
            os.link(out.name, path)
    trusted(path)
    require(path.read_bytes() == expected, "existing runtime file differs: " + str(path))


def unit(stage, cfg, apply):
    name = "cth-web.service" if stage == "services" else "cth-ingress.service"
    dest = UNIT_DIR / name
    if not os.path.lexists(dest):
        require(command("systemctl", "show", "--property=LoadState", "--value", name, ok=(0, 4)) == "not-found",
                "another systemd unit already uses the selected name")
    managed(dest, name, cfg, apply)
    if apply:
        command("systemd-analyze", "verify", str(dest))
        command("systemctl", "daemon-reload")
    require(command("systemctl", "show", "--property=FragmentPath", "--value", name) == str(dest)
            and not command("systemctl", "show", "--property=DropInPaths", "--value", name),
            "unexpected active unit definition")
    if apply:
        command("systemctl", "enable", "--now", name)
    command("systemctl", "is-enabled", "--quiet", name)
    command("systemctl", "is-active", "--quiet", name)


def await_start(name, check):
    deadline = time.monotonic() + 25
    while True:
        try:
            return check()
        except ValueError:
            failed = command("systemctl", "is-failed", name, ok=(0, 1, 3))
            if failed == "failed" or time.monotonic() >= deadline:
                raise
            time.sleep(1)


def curl(url, *options):
    return command("curl", "--disable", "--noproxy", "*", "--silent", "--show-error", "--max-time", "8",
                   "--max-filesize", "65536", *options, url)


def local_health(cfg, tls=False):
    address = "http://127.0.0.1:8000"
    args = ["--fail"]
    if tls:
        name = cfg["hostname"]
        address = "https://" + name
        port = 443
        args += ["--connect-to", f"{name}:443:127.0.0.1:{port}"]
    require(curl(address + "/health", *args) == "ok", "database health failed")
    signals = json.loads(curl(address + "/health/status", *args))["signals"]
    known = [s for s in signals if s.get("epistemic_state") == "KNOWN"]
    require(len(known) == 1 and known[0].get("key") == "database" and known[0].get("outcome") == "PASS"
            and len(signals) > 1 and all(s in known or s.get("outcome") == "UNKNOWN" for s in signals),
            "unexpected bounded health response")


def scheduler(cfg):
    query = """SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a USING (pid)
               WHERE l.locktype='advisory' AND l.granted AND l.objsubid=1
               AND l.database=(SELECT oid FROM pg_database WHERE datname=current_database())
               AND ((l.classid::bigint << 32) | l.objid::bigint)=7425163849122001 AND a.usename='cthapp'"""
    require(command("runuser", "-u", "cthapp", "--", "psql", "-XAtw", "-v", "ON_ERROR_STOP=1",
                    "-h", "/var/run/postgresql", "-p", "5432", "-d", cfg["database"], "-c", query) == "1",
            "expected one scheduler advisory-lock owner in the enrolled database")
    invocation = command("systemctl", "show", "-p", "InvocationID", "--value", "cth-web.service")
    require(re.fullmatch("[0-9a-f]{32}", invocation), "missing active web service invocation")
    lines = command("journalctl", "--quiet", "--no-pager", "--reverse", "-o", "cat", "_SYSTEMD_INVOCATION_ID=" + invocation,
                    "--grep=Scheduler started in pid", "-n", "1")
    require("this process holds the scheduler lock" in lines, "scheduler startup evidence missing")


def storage_controls():
    name = "cth-web.service"
    for key in ("LimitCORE", "MemorySwapMax"):
        require(command("systemctl", "show", "--value", "-p", key, name) == "0", "missing worker limit: " + key)
    group = command("systemctl", "show", "--value", "-p", "ControlGroup", name)
    require(group == "/system.slice/cth-web.service" and
            (Path("/sys/fs/cgroup") / group.lstrip("/") / "memory.swap.max").read_text().strip() == "0",
            "worker cgroup v2 swap limit is not effective")


def inspect_listeners(port, address="127.0.0.1"):
    lines = command("ss", "-H", "-ltn", "sport", "=", ":" + str(port)).splitlines()
    require(len(lines) == 1 and lines[0].split()[3] == f"{address}:{port}",
            f"expected single listener on {address}:{port}")


def inspect_ingress(cfg):
    inspect_listeners(443, "0.0.0.0")


def run(action, stage, cfg):
    validate_config(cfg)
    trusted(cfg["runtime_env"], secret=True)
    parse_env(Path(cfg["runtime_env"]).read_text(), cfg)
    release = Path("/opt/cth/releases") / cfg["release_sha"]
    require(not os.path.lexists(release / ".env"), "release contains a dotenv override")
    apply = action == "apply"
    require(action in ("apply", "check"), "unknown action")
    if stage == "config":
        return
    if stage == "services":
        for sock in (SETUP_SOCKET, RATE_SOCKET):
            require(command("runuser", "-u", "cthapp", "--", "redis-cli", "-s", sock, "PING") == "PONG",
                    "Redis socket unavailable to service account")
        unit(stage, cfg, apply)
        await_start("cth-web.service", lambda: inspect_listeners(8000))
        await_start("cth-web.service", lambda: local_health(cfg))
        storage_controls()
    elif stage == "scheduler":
        await_start("cth-web.service", lambda: scheduler(cfg))
    elif stage == "ingress":
        trusted(cfg["tls_key"], secret=True)
        trusted(cfg["tls_cert"])
        command("openssl", "x509", "-in", cfg["tls_cert"], "-checkend", "0", "-noout")
        require(command("systemctl", "is-enabled", "nginx.service", ok=(0, 1)) == "masked"
                and command("systemctl", "is-active", "nginx.service", ok=(0, 3)) == "inactive",
                "stock nginx must be masked and inactive")
        local_health(cfg)
        managed(Path("/etc/cth/ingress.conf"), "ingress.conf", cfg, apply)
        unit(stage, cfg, apply)
        await_start("cth-ingress.service", lambda: inspect_ingress(cfg))
        await_start("cth-ingress.service", lambda: local_health(cfg, tls=True))
    elif stage == "readiness":
        for name in ("cth-web.service", "cth-ingress.service"):
            command("systemctl", "is-active", "--quiet", name)
        inspect_listeners(8000)
        inspect_ingress(cfg)
        storage_controls()
        local_health(cfg)
        local_health(cfg, tls=True)
        scheduler(cfg)
    else:
        raise ValueError("unknown runtime stage")
