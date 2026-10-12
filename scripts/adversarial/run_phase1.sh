#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

: "${ADVERSARIAL_RUN_ID:=current}"
: "${ADVERSARIAL_ARTIFACT_DIR:=artifacts/adversarial}"

RUN_DIR="${ADVERSARIAL_ARTIFACT_DIR}/${ADVERSARIAL_RUN_ID}"
mkdir -p "$RUN_DIR"
# Keep per-run scorecards deterministic by resetting mutable violation output.
: > "$RUN_DIR/violations.jsonl"
# A crashed verifier must not leave a previous run's PASS available to the scorecard.
rm -f "$RUN_DIR/injection_report.json" "$RUN_DIR/cross_class_report.json" \
  "$RUN_DIR/lineage_report.json" "$RUN_DIR/runtime_attacks_report.json" "$RUN_DIR/scorecard.md"

status=0
"${PYTHON_BIN}" -m scripts.adversarial.inject_impossible_state || status=1
"${PYTHON_BIN}" -m scripts.adversarial.verify_cross_class_isolation || status=1
"${PYTHON_BIN}" -m scripts.adversarial.verify_lineage_lawfulness || status=1
"${PYTHON_BIN}" -m scripts.adversarial.verify_runtime_session_attacks || status=1
"${PYTHON_BIN}" -m scripts.adversarial.render_constitutional_scorecard || status=1
"${PYTHON_BIN}" -m scripts.adversarial.build_evidence_bundle --run-id "$ADVERSARIAL_RUN_ID"

echo "Phase 1 harness run complete for run_id=$ADVERSARIAL_RUN_ID"

exit "$status"
