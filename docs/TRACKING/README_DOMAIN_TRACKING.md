# Tracking Documents

**Effective:** 2026-09-03 (amended 2026-09-28, after launch; 2026-10-22, backlog moved to GitHub)
**Replaces:** the `DOMAIN_PROGRESS_MATRIX_2026.md` system (archived 2026-09-03)

---

## What lives here

`docs/TRACKING/` holds **only live, forward-looking work**. Completed phase notes, point-in-time
audits, and superseded plans live in [`docs/archive/v2-tracking-2026/`](https://github.com/timwonderer/classroom-token-hub/tree/main/docs/archive/v2-tracking-2026).

| File | Purpose |
|---|---|
| [`BATCH-B_OPERATIONS_VERIFIER_POLICY_DECISION_PACKAGE_20260901.md`](BATCH-B_OPERATIONS_VERIFIER_POLICY_DECISION_PACKAGE_20260901.md) | Approved Operations verifier policy decisions, cited by SOP-DOC-001. |
| [`FEAT_REGISTRY_RECONCILIATION_2026-09-19.md`](FEAT_REGISTRY_RECONCILIATION_2026-09-19.md) | FEAT registry against implementation, cited from `app/feats/`. |
| [`DOCS_PLATFORM_ROADMAP.md`](DOCS_PLATFORM_ROADMAP.md) | Documentation platform plan. |
| [`DOMAIN_IMPLEMENTATION_PLAN_TEMPLATE.md`](DOMAIN_IMPLEMENTATION_PLAN_TEMPLATE.md) | Reusable SOP-DEV-002 plan template for a single domain. |

The pre-launch ship tracker, `PRODUCTION_READINESS_2026-09.md`, was archived on 2026-09-28 after
v2.0.0 and v2.0.1 shipped. Its open items were re-verified and carried into the post-launch
tracker. That tracker was archived in turn on 2026-10-22: **the backlog is GitHub Issues and the
[CTH Backlog](https://github.com/users/timwonderer/projects/6) project**, not a file here. Release and audit records are not tracking
documents; they live in `docs/ops/audits/`.

---

## Rules

### 1. Readiness is judged from the normative documents, never from a tracker

Authority flows `INV-CORE → INV-ARC → DOM → FEAT`. A tracker records findings; it does not confer
status. When a tracker and a normative document disagree, the document wins and the tracker is
corrected. When a normative document and the code disagree, the document defines the target state
and the gap is a finding against the code.

### 2. Amend, do not accumulate

The previous system failed because each sprint minted a new dated document while the nominally
canonical one silently went stale — by 2026-09-03 the matrix was wrong about four domains, and the
post-launch tracker stopped at v2.1.1. Open work is an issue on the CTH Backlog project; close it with
the PR or commit that resolves it.

### 3. Archive on completion, never delete

When a document stops describing live work, `git mv` it to `docs/archive/v2-tracking-2026/` and add
a line to that directory's README explaining why.

### 4. Ephemeral domain plans are fine

Copy the template for one domain's migration, then archive it when the domain certifies. Do not let
it become a second source of truth.

---

## Working a domain

1. Read the domain's normative spec (`docs/DOMAIN/DOM-*.md`) and the invariants it cites.
2. Read the domain's open issues on the CTH Backlog project.
3. If the work spans multiple phases, copy `DOMAIN_IMPLEMENTATION_PLAN_TEMPLATE.md`.
4. Land the fix with a regression test that fails against the pre-fix commit.
5. Close the issue with the PR that fixes it.
