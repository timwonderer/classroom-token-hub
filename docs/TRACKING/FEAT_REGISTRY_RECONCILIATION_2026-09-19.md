# FEAT Registry Reconciliation — 2026-09-19

**Status:** Post-launch architectural reconciliation — known at launch, deliberately deferred.
One item (§V) was resolved before launch; every other disposition below is frozen and remains
proposed-but-undecided. Preserved in that state on purpose.
**Scope:** `app/feats/base.py` `FEAT_REGISTRY` against `docs/FEATURE-EXECUTION/`
**Authority:** None. This is a descriptive record. `INV-CORE-001` and `FEAT-CORE-000` govern what a
FEAT is; `DOM-CORE-001` governs which domain owns what. Where this document and any of those
disagree, they win and this document is what gets corrected.

---

## I. Why this exists

`INV-ARC-000` §VIII.2 records every request's domain, capability and action from the FEAT it
executes under, and `FEAT-CORE-000` makes the FEAT the unit a user-facing action is named by. Two
things follow that nothing currently checks:

1. A FEAT that executes without a contract document is an unwritten law that the audit trail cites
   by number.
2. A contract with no registry entry is a law with no executor — either unimplemented, or
   implemented under a different id, which makes the audit trail name the wrong action.

The registry holds **46** ids; `docs/FEATURE-EXECUTION/` holds **40** contracts. They overlap on 35.

This audit was prompted by `FEAT-SETTINGS-001`, found while checking navigation targets for the
developer documentation site.

---

## II. Summary

| Category | Count | Disposition needed |
|---|---:|---|
| Registered **and** contracted | 35 | None |
| Registered, self-labelled `[RETIRED → …]` | 3 | Confirm removal date |
| Registered, no contract, **executing in app code** | 6 | Deferred — 1 of 6 resolved (§V) |
| Registered, no contract, no execution | 2 | **Yes** |
| Contracted, not registered — constitutional directive | 1 | None |
| Contracted, not registered — id collision | 1 | **Yes** |
| Contracted, not registered — feature exists under other ids | 2 | **Yes** |
| Contracted, not registered — delegated | 1 | Confirm |

---

## III. Registered, no contract — executing in app code

These run in production and are named in audit rows. Each needs a contract, a rename onto an
existing contract, or a documented reason it is exempt.

| Id | Registry | Executions | Evidence | Proposed disposition |
|---|---|---:|---|---|
| `FEAT-SETTINGS-001` | Class Configuration · MED · "Class Settings Update" | 6 | `app/feats/attendance.py:71,115`; `app/routes/admin.py:4433,4915,5006,5163` | **Split.** The id predates the `FEAT-CLASS-*` namespace (registry 2026-07-21; namespace 2026-08-12). Feature-enablement callers move to `FEAT-CLASS-004`; the remaining settings writes (hall-pass config, store catalog, rent policy) get a new `FEAT-CLASS-007` with a contract. See §VI. |
| `FEAT-OBL-001` | Obligations · MED · "Rent Payment" | 2 | `app/feats/rent_payment_feat.py:525,544` | **RESOLVED 2026-09-19** — see §V. Rent payment keeps this id and still has no contract; that half stays deferred. |
| `FEAT-OBL-005` | Obligations · MED · "Insurance Cancellation (stop renewal)" | 1 | `app/feats/cancel_insurance_feat.py:78` | Write the contract. Cancellation semantics are settled (EXPIRED-only at cycle boundary, non-revocable); the contract records them. |
| `FEAT-ADMN-001` | Logistics · LOW · "Bulk administration" | 1 | `app/routes/admin.py:7436` | **Question the domain first.** "Logistics" appears in no `DOM-*` document. Either the domain is real and undocumented, or this belongs to Class Configuration. |
| `FEAT-IDEN-005` | Identity · MED · "Authenticated Class Binding" | 1 | `app/feats/identity_feat.py:462` | Write the contract, or fold into `FEAT-IDEN-002` if class binding is already that workflow. |
| `FEAT-LED-003` | Ledger · HIGH · "Settlement Sweep" | 0 in app, 8 in tests | `docs/TRACKING/LEDGER_SERVICE_FEAT_CONSOLIDATION_20260904.md` | HIGH blast radius with no production caller. Decide whether it is live, or a test-only fixture that should not hold a HIGH id. |

## IV. Registered, no contract — not executing

| Id | Registry | Proposed disposition |
|---|---|---|
| `FEAT-LED-004` | Ledger · HIGH · "Payroll Execution" | **Remove.** `MAP-UI-001` records the payroll route as rewired off it on 2026-07-21; two test references remain. |
| `FEAT-ITR-001` | Interpretation · LOW · "Compute Interpretation Snapshot" | **Keep, write the contract when slice 8.3 lands.** `DOM-ITR-001` and `SPEC-ITR-001` already name it; the executor is mid-build. |

### Self-labelled retirements — no action beyond confirming they may be deleted

`FEAT-ENT-001` (`[RETIRED → FEAT-STOR-001]`), `FEAT-STOR-005` and `FEAT-STOR-006`
(`[RETIRED → FEAT-STOR-002]`). Zero references anywhere. They are tombstones kept to stop the
numbers being reused; if that is the intent it belongs in a comment, not in a registry that
`requires_feat_context` will happily accept.

---

## V. `FEAT-OBL-001` versus `FEAT-OBLI-001` — RESOLVED 2026-09-19

Two ids one letter apart, in the same domain, naming different workflows:

- `FEAT-OBL-001` — registry only. "Rent Payment".
- `FEAT-OBLI-001` — contract only (v1.1, 2026-07-24). "Assess Obligation": creates the immutable
  `event_type = ASSESSMENT` row and hands settlement to `FEAT-OBL-003`.

`app/feats/assess_obligation_feat.py` implemented the *second* and executed under the *first*, and
its comment cited "FEAT-OBL-001 §V" — a section of a document that does not exist.

### Severity, stated accurately

The initial reading of this audit said assessment events were being audited as rent payments. That
overstates it, and the correction matters for a launch decision:

- `execute_assess_obligation` — the mislabelled entry point — **has no production caller.** Only
  tests reach it.
- Production assessments reach `assess_obligation` directly from `reconcile_rent_feat`
  (`FEAT-OBL-002`), `purchase_insurance_feat` (`FEAT-OBL-004`) and `nsf_fee_feat` (inside its
  caller's context). Those attribute to the workflow that created the obligation, which is correct.
- Assessments write no Ledger effect (`ledger_transaction_id` is NULL for ASSESSMENT), so no
  `ledger_command_reservation` identity — `UNIQUE(class_id, feat_code, idempotency_key)` — depended
  on the wrong code.

So the defect was **latent, not live**: wrong lineage the first time a route called the public
entry point, and nothing before then.

### The change made

The smallest change consistent with the existing contract, and nothing else:

1. `FEAT-OBLI-001` registered in `FEAT_REGISTRY` as its own workflow — Obligations, MED, "Assess
   Obligation" — with a comment recording why the two ids must not be tidied into one another.
2. `execute_assess_obligation` re-decorated onto `FEAT-OBLI-001`.
3. The in-code citation corrected to `FEAT-OBLI-001` §V, which exists and is the audit-requirements
   section it meant.

No obligations refactor, no renaming of either concept, no change to rent payment, and no migration:
`feat_code` is written forward from the active context, and rows already written keep what they
carry.

`tests/dom/obligations/test_assessment_feat_attribution.py` holds the attribution, the assessment
row that must survive the re-labelling, and the adjacent surfaces that must not move
(`FEAT-OBL-001` on rent payment, `FEAT-OBL-002`/`FEAT-OBL-004` on the scheduled cycles). The
attribution test was watched failing against the old decorator.

**Still deferred:** which concept ultimately keeps which number, and the missing `FEAT-OBL-001`
contract for rent payment. Nothing above forecloses either decision.

---

## VI. Contracted, not registered

| Id | Contract | Reading |
|---|---|---|
| `FEAT-CORE-000` | Feature Execution Constitutional Directive (2026-04-23) | Correct as-is. It defines what a FEAT *is*; it is not itself executable. |
| `FEAT-IDEN-102` | Teacher Passkey Enrollment (v1.0, 2026-08-09, `Status: NEW`) | Passkey code exists (`app/utils/passwordless_client.py`, `app/auth.py`) but runs under no FEAT id. Either register these two, or record that enrollment happens inside `FEAT-IDEN-101`. |
| `FEAT-IDEN-107` | Teacher Revoke Passkey (v1.0, 2026-08-09, `Status: NEW`) | As above. |
| `FEAT-ECON-001` | Economic Policy Transition and Activation Orchestration (v2.1, 2026-09-15) | Actively cited by `app/utils/economy_rebalance.py` and `app/services/admin_settings_service.py`, and `FEAT-CLASS-005` lists it as a composing FEAT that "may delegate to this FEAT". Confirm whether it executes through `FEAT-CLASS-005` — if so, say so in the contract. |
| `FEAT-OBLI-001` | Assess Obligation | See §V. |

---

## VII. What a decision here should produce

1. One id per workflow, spelled one way, present in both the registry and `docs/FEATURE-EXECUTION/`.
2. A test that fails when the two disagree, in the shape of
   `tests/dom/docs/test_documentation_index_complete.py`. The gap above is invisible at runtime —
   `requires_feat_context` accepts any registered id, and an unregistered contract breaks nothing —
   so it can only be caught by comparing the two lists.
3. `SOP-DOC-001` picks up each new contract automatically once it exists; that index is now gated.

§V is done. Everything else here is post-launch work and needs a domain-ownership ruling on
§III, §IV and §VI before anyone touches it. Discovering this debt near launch did not create an
obligation to clear it near launch — only to find the part that could affect correctness now,
which was §V.
