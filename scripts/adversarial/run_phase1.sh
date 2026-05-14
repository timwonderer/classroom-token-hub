#!/usr/bin/env bash
set -euo pipefail

: "${ADVERSARIAL_RUN_ID:=current}"

python3 scripts/adversarial/inject_impossible_state.py
python3 scripts/adversarial/verify_cross_class_isolation.py || true
python3 scripts/adversarial/verify_lineage_lawfulness.py || true
python3 scripts/adversarial/verify_runtime_session_attacks.py || true
python3 scripts/adversarial/render_constitutional_scorecard.py
python3 scripts/adversarial/build_evidence_bundle.py --run-id "$ADVERSARIAL_RUN_ID"

echo "Phase 1 harness run complete for run_id=$ADVERSARIAL_RUN_ID"
