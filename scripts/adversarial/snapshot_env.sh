#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <snapshot_name>"
  exit 1
fi

python3 scripts/adversarial/snapshot_db.py --name "$1"
