#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <snapshot_dir> <database_url>"
  exit 1
fi

python3 scripts/adversarial/reset_db.py --snapshot-dir "$1" --database-url "$2"
