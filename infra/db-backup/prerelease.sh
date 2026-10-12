#!/usr/bin/env bash
# Pre-release backup and restore check from the operator's Mac (SOP-DEP-002 §VII.A steps 5-7).
#
#   bash infra/db-backup/prerelease.sh backup    # stops the app, takes and verifies one point
#   bash infra/db-backup/prerelease.sh counts    # compares that point's table counts with live production
#   bash infra/db-backup/prerelease.sh restore   # restores it with ~/cth-backup/identity.txt, then deletes the identity
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

latest() { ls -t ~/cth-backup/prerelease-*/points/*."$1" 2>/dev/null | head -1; }

case "${1:-}" in
backup)
  pg_dump --version
  if lsof -nP -iTCP:55433 -sTCP:LISTEN >/dev/null; then
    echo "port 55433 is already in use (a leftover tunnel?): close it first"; exit 1
  fi
  docker rm -f cth-verify >/dev/null 2>&1 || true
  docker run --rm -d --name cth-verify -e POSTGRES_PASSWORD=verify \
    -p 127.0.0.1:55432:5432 --tmpfs /var/lib/postgresql/data postgres:14
  sleep 5
  docker exec cth-verify createdb -U postgres cth_backup_verify
  docker exec cth-verify createdb -U postgres cth_restore_check

  ssh -f -N -o ExitOnForwardFailure=yes -L 55433:127.0.0.1:5432 root@cth
  ssh root@cth 'systemctl stop classroom-economy; systemctl is-active classroom-economy || true'

  "$PY" "$TOOL" backup --reason manual 2>&1 | sed -E "$REDACT"
  latest manifest.json
  ;;
counts)
  # Live counts must be read with the application still stopped, or they drift from the point.
  M=$(latest manifest.json)
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
  [ -f "$ID" ] || { echo "missing $ID"; exit 1; }
  trap 'rm -P "$ID"; echo "identity deleted"' EXIT
  diff <(age-keygen -y "$ID") "$CTH_BACKUP_AGE_RECIPIENTS_FILE" >/dev/null \
    || { echo "identity does not match recipients.txt"; exit 1; }
  P=$(latest dump.age)
  "$PY" "$TOOL" restore \
    --artifact "$P" --manifest "${P%.dump.age}.manifest.json" --identity "$ID" \
    --target-url 'postgresql://postgres:verify@127.0.0.1:55432/cth_restore_check' \
    --live-url "$CTH_BACKUP_SOURCE_URL" 2>&1 | sed -E "$REDACT"
  docker stop cth-verify
  ;;
*) echo "usage: $0 backup|counts|restore"; exit 2 ;;
esac
