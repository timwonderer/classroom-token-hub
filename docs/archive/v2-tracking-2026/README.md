# Archive — v2 Migration and Launch Tracking (2026-07 → 2026-09)

Historical, **non-authoritative** working documents from the v2 domain migration. Retained for
provenance only. Nothing here describes current system state.

First archived 2026-09-03, when `docs/TRACKING/` was reset around a single ship tracker. A second
batch followed on 2026-09-28, after v2.0.0 (2026-09-26) and v2.0.1 (2026-09-28) shipped and that
ship tracker had done its job.

**Current canonical tracker:** [`docs/TRACKING/POST_LAUNCH_TRACKER_2026.md`](../../TRACKING/POST_LAUNCH_TRACKER_2026.md)

## Why these were archived

- `DOMAIN_PROGRESS_MATRIX_2026.md` — the previous canonical tracker. Last updated 2026-08-20 and
  materially wrong by 2026-09-03: it listed Interpretation, Operations, and Support as NOT STARTED
  and Ledger and Payroll as BLOCKED, all contradicted by the code on this branch.
- `PHASE1_*`, `PHASE3_*`, `PHASE4_*`, `CLASS_CONFIG_PHASE3_*`, `CLASS_PHASE2_*` — SOP-DEV-002 phase
  working notes for phases that have since completed.
- `SOP-DEV-002*_AUDIT.md`, `*_QA_AUDIT*.md`, `AUDIT_BASELINE_2026-08-04.md`,
  `V2_REBUILD_VALIDATION_REPORT.md` — point-in-time audits superseded by the 2026-09-03
  doc-authoritative readiness audit.
- `V2_BUILD_SPEC/`, `V2_Full_compliance_migration_plan.md`, `V2_REMEDIATION_PLAN_2026-07-16.md`,
  `INV-ARC_CONSOLIDATION_AND_CANONICAL_OBJECT_STRATEGY.md` — planning documents whose conclusions
  were absorbed into the normative `INV-*` and `DOM-*` documents. **Read the normative docs, not
  these.**
- `TEMPLATE_AUDIT_FOR_REWIRING/`, `TEMPLATE_JINJA_INVENTORY.md`, `TERMINOLOGY_AUDIT_V1.md` —
  completed inventory sweeps.
- `DOM_ECON_ARCHAEOLOGY_2026-08-16.md`, `INTERPRETATION_METRIC_RECOVERY_2026-08-16.md`,
  `OBLIGATION_POLICIES_FOLLOWUP_2026-08-16.md`, `DOM-ITR_PAYROLL_CYCLE_LIFECYCLE_HANDOFF_2026-08-30.md`
  — investigation and session-handoff notes whose outcomes have landed.
- `PYTEST_BASELINE_dc5e0efb.md` — test baseline for a commit far behind current HEAD.

### Archived 2026-09-28 (after launch)

- `PRODUCTION_READINESS_2026-09.md` — the pre-launch ship tracker (canonical 2026-09-03 → 2026-09-28).
  Its blocking issues B1–B11 are all closed and v2 has shipped. The items still open were
  re-verified against the code and carried into `POST_LAUNCH_TRACKER_2026.md`. The live-test
  campaign evidence it summarises stays in `docs/ops/audits/`.
- `ACCESSIBILITY_REVIEW_2026-09-03.md` — point-in-time review. Its "remaining issues" predate the
  axe coverage of every rendered template (`tests/test_axe_app_pages.py`) and the SOP-TEST-002
  accessibility gate.
- `CI_CLASSIFIER_DESIGN_2026-08-26.md`, `CI_EVIDENCE_REUSE_MATRIX_2026-08-26.md` — a design marked
  "implementation not started" and its frozen input. Both are implemented:
  `scripts/ci_classifier.py`, `scripts/ci_evidence_runner.py` and
  `.github/workflows/constitutional-ci.yml` under SPEC-INV-001.
- `USER_GUIDE_INVENTORY_2026-09.md`, `USER_GUIDE_COVERAGE_2026-09.md` — phase trackers for the
  user-guide rebuild, now complete. `docs/user-guides/` and `docs/self-hosting/` are the result.
- `PUBLIC_PRIVACY_DISTRICT_AUDIT_20260915.md` — finished audit of the public privacy and district
  pages, whose fixes landed in `github-pages/`.
- `V2_LEDGER_BALANCE_CONTRACT_RESOLUTION_20260831.md` — a proposal "pending DOM-LED-001 review" that
  was adopted: DOM-LED-001 defines `posted_balance_cents`, and `LedgerBalanceSnapshot` carries
  `reconciled_through_posting_sequence`.
- `V2_INVARIANT_VERIFIER_RECONCILIATION_20260831.md` — its own §VIII records the v1-to-v2 semantic
  reconciliation as closed and hands off to the BATCH-B package.
- `LEDGER_SERVICE_FEAT_CONSOLIDATION_20260904.md` — working inventory for the ledger service
  consolidation. The target `ledger_*_service.py` modules exist, and `balance_service.py` and
  `ledger_service.py` are gone.
- `STATUS_SIMPLIFICATION_PLAN.md` (formerly `docs/ops/`) — implementation plan for the status-page
  simplification that shipped 2026-09-21 (#1422). Its validation run record moved to
  `docs/ops/audits/STATUS_SIMPLIFICATION_VALIDATION_2026-09-22.md`.

`MAP-CLASS-002` (class-scope normalization target) was archived the same day to
`docs/archive/MAP/`. The `class_id`-first model it described as a future target is the current
model, governed by INV-ARC-019 and DOM-IDEN-001.
