#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-.env.redteam.local}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

: "${DATABASE_URL:?DATABASE_URL must be set in $ENV_FILE}"
: "${ADVERSARIAL_RUN_ID:=current}"
: "${ADVERSARIAL_SNAPSHOT_DIR:=artifacts/adversarial/snapshots}"
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x "venv/bin/python" ]]; then
    PYTHON_BIN="venv/bin/python"
  elif [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

echo "Using DATABASE_URL=${DATABASE_URL/@*/@***redacted***}"
echo "Using PYTHON_BIN=${PYTHON_BIN}"

echo "[1/4] snapshot golden_base"
"${PYTHON_BIN}" scripts/adversarial/snapshot_db.py --name golden_base

echo "[2/4] seed minimal phase1 topology"
"${PYTHON_BIN}" scripts/adversarial/seed_phase1_minimal.py --env-file "$ENV_FILE"

echo "[3/4] snapshot seeded_base"
"${PYTHON_BIN}" scripts/adversarial/snapshot_db.py --name seeded_base

echo "[4/4] done"
echo "Snapshots written under: ${ADVERSARIAL_SNAPSHOT_DIR}"
