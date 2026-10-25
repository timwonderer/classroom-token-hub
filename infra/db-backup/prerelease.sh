#!/usr/bin/env bash
# Pre-release backup and restore check from the operator's Mac (SOP-DEP-002 §VII.A steps 5-7).
#
#   bash infra/db-backup/prerelease.sh backup    # stops the app, takes and verifies one point
#   bash infra/db-backup/prerelease.sh counts    # compares that point's table counts with live production
#   bash infra/db-backup/prerelease.sh restore   # restores it with ~/cth-backup/identity.txt, then deletes the identity
#   bash infra/db-backup/prerelease.sh close-tunnel   # closes the tunnel if a run is abandoned before `restore`
#
# All three steps reach production through one SSH tunnel (127.0.0.1:55433), owned through a control socket so it
# can be checked and closed exactly. `backup` opens it and keeps it open on success for `counts` and `restore`;
# `restore` closes it on exit. Until 2026-10-22 nothing closed it: the v2.2.4 tunnel was still listening six days
# later and blocked the v2.3.0 backup.
#
# Reads the source URL from ~/cth-backup/source_url (mode 600), so nobody types a password. Before `restore`, the
# operator copies the age key to the clipboard and runs:  umask 077; pbpaste > ~/cth-backup/identity.txt
# The application stays stopped; the release workflow restarts it.
set -euo pipefail

export PATH=/opt/homebrew/opt/postgresql@14/bin:$PATH   # client major must match the server (14)
export DOCKER_HOST=${DOCKER_HOST:-unix://$HOME/.colima/default/docker.sock}
export CTH_BACKUP_SOURCE_URL="$(cat ~/cth-backup/source_url)"
export CTH_BACKUP_VERIFY_URL='postgresql://postgres:verify@127.0.0.1:55432/cth_backup_verify'
export CTH_BACKUP_AGE_RECIPIENTS_FILE=~/cth-backup/recipients.txt
export CTH_BACKUP_STATE_DIR=${CTH_BACKUP_STATE_DIR:-~/cth-backup/prerelease-$(date -u +%F)}
unset CTH_BACKUP_REMOTE
PY=~/cth-backup-venv/bin/python
TOOL="$(cd "$(dirname "$0")" && pwd)/cth_db_backup.py"
REDACT='s#postgresql://[^ ]*@#postgresql://[redacted]@#g'
SOCK=~/cth-backup/tunnel.sock

tunnel_up() { [ -S "$SOCK" ] && ssh -S "$SOCK" -O check root@cth 2>/dev/null; }
open_tunnel() {
  tunnel_up && return 0
  # A socket left by a reboot or an unclean exit has no master behind it. Starting a new master on that path
  # would make ssh continue without one, an uncontrollable tunnel, so remove it first and check the result.
  rm -f "$SOCK"
  ssh -f -N -M -S "$SOCK" -o ExitOnForwardFailure=yes -L 55433:127.0.0.1:5432 root@cth
  tunnel_up || { echo "the tunnel started without its control socket; close it: lsof -nP -iTCP:55433 -sTCP:LISTEN"; exit 1; }
}
close_tunnel() {
  if tunnel_up; then ssh -S "$SOCK" -O exit root@cth 2>/dev/null || true; echo "tunnel closed"; fi
  rm -f "$SOCK"
}

latest() { ls -t "$CTH_BACKUP_STATE_DIR"/points/*."$1" 2>/dev/null | head -1 || true; }   # this run's state dir only

case "${1:-}" in
backup)
  pg_dump --version
  if ! tunnel_up && lsof -nP -iTCP:55433 -sTCP:LISTEN >/dev/null; then
    echo "port 55433 is already in use by something this script does not own (a tunnel from before control"
    echo "sockets?): close it first, e.g. lsof -nP -iTCP:55433 -sTCP:LISTEN"; exit 1
  fi
  docker rm -f cth-verify >/dev/null 2>&1 || true
  docker run --rm -d --name cth-verify -e POSTGRES_PASSWORD=verify \
    -p 127.0.0.1:55432:5432 --tmpfs /var/lib/postgresql/data postgres:14
  sleep 5
  docker exec cth-verify createdb -U postgres cth_backup_verify
  docker exec cth-verify createdb -U postgres cth_restore_check

  open_tunnel
  trap 'close_tunnel' ERR   # a failed backup leaves nothing open; a successful one keeps it for counts and restore
  # Refuse to back up while the app could still be writing.
  ssh root@cth 'systemctl stop classroom-economy; ! systemctl is-active --quiet classroom-economy' \
    || { echo "classroom-economy is still active: not backing up"; close_tunnel; exit 1; }
  echo "classroom-economy inactive"

  "$PY" "$TOOL" backup --reason manual 2>&1 | sed -E "$REDACT"
  trap - ERR
  latest manifest.json
  ;;
counts)
  # Live counts must be read with the application still stopped, or they drift from the point.
  M=$(latest manifest.json); [ -n "$M" ] || { echo "no point in $CTH_BACKUP_STATE_DIR (set CTH_BACKUP_STATE_DIR to the backup's directory)"; exit 1; }
  open_tunnel
  python3 - "$M" <<'EOF' | psql -X -q -At -F' ' "$CTH_BACKUP_SOURCE_URL" > /tmp/cth_live_counts.$$
import json, sys
tables = sorted(json.load(open(sys.argv[1]))["table_counts"])
print(" UNION ALL ".join(f"SELECT '{t}', count(*) FROM public.\"{t}\"" for t in tables) + ";")
EOF
  python3 - "$M" /tmp/cth_live_counts.$$ <<'EOF'
import json, sys
m = json.load(open(sys.argv[1]))
live = {t: int(n) for t, n in (line.split() for line in open(sys.argv[2]) if line.strip())}
bad = {t: (n, live.get(t)) for t, n in m["table_counts"].items() if live.get(t) != n}
print(m["stem"], "revision", m["alembic_revision"], "sha256", m["artifact_sha256"])
print(f"{len(m['table_counts'])} tables, {sum(m['table_counts'].values())} rows;",
      "manifest == live" if not bad else f"MISMATCH {bad}")
sys.exit(1 if bad else 0)
EOF
  rm -f /tmp/cth_live_counts.$$
  ;;
restore)
  ID=~/cth-backup/identity.txt
  # Last step: the tunnel is closed and any identity deleted however this exits, including the guards below.
  trap 'if [ -f "$ID" ]; then { rm -P "$ID" 2>/dev/null || rm -f "$ID"; }; echo "identity deleted"; fi; close_tunnel' EXIT
  [ -f "$ID" ] || { echo "missing $ID"; exit 1; }
  diff <(age-keygen -y "$ID") "$CTH_BACKUP_AGE_RECIPIENTS_FILE" >/dev/null \
    || { echo "identity does not match recipients.txt"; exit 1; }
  P=$(latest dump.age); [ -n "$P" ] || { echo "no point in $CTH_BACKUP_STATE_DIR (set CTH_BACKUP_STATE_DIR to the backup's directory)"; exit 1; }
  open_tunnel   # --live-url reaches production through it for the no-resurrection check
  "$PY" "$TOOL" restore \
    --artifact "$P" --manifest "${P%.dump.age}.manifest.json" --identity "$ID" \
    --target-url 'postgresql://postgres:verify@127.0.0.1:55432/cth_restore_check' \
    --live-url "$CTH_BACKUP_SOURCE_URL" 2>&1 | sed -E "$REDACT"
  docker stop cth-verify
  ;;
close-tunnel)
  close_tunnel
  ;;
*) echo "usage: $0 backup|counts|restore|close-tunnel"; exit 2 ;;
esac
