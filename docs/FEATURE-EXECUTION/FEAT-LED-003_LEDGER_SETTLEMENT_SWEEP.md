# FEAT-LED-003: Ledger Settlement Sweep

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-LED-003 | 1.0 | 2026-11-24 | — | Normative |

---

## I. Purpose

`FEAT-LED-003` is the scheduled Settlement Sweep: the sole mechanism that admits `PENDING` ledger effects to `POSTED` history and advances each `(class_id, seat_id, account_type)` `LedgerBalanceSnapshot`'s reconciliation cursor (`app/services/ledger_settlement_service.py::settle_pending_transaction_contexts` / `settle_balances`). Nothing else performs this admission; without it no transaction ever posts and every posted-balance read answers zero (`DOM-LED-001` §VI, INV-LED-004, INV-LED-006).

It runs on its own schedule (`run_ledger_settlement_job`) and is also invoked synchronously, as the same command, at the top of the Savings Interest job (`run_savings_interest_job`) immediately before interest accrual — interest is computed from posted balances only (`SPEC-ECON-001` §9.2), and the two jobs have no ordering guarantee between their own independent schedules, so the dependency is discharged by calling this FEAT directly rather than trusting registration order.

The name `FEAT-LED-003` already appeared in code (`settle_pending_transaction_contexts`'s docstring) before this document existed; this contract formalizes the open slot that code already claimed.

---

## II. Scope

Every `(class_id, seat_id)` context carrying `PENDING` ledger activity, across every class. Each context settles inside its own `FEAT-LED-003` transaction boundary, so one context's failure is isolated: it neither rolls back nor blocks any other context's settlement in the same sweep.

This FEAT does not decide business eligibility for any effect; it only reconciles what `FEAT-LED-001` (and other Ledger-posting commands) already accepted as `PENDING`.

---

## III. Authority Level

Normative; subordinate to `INV-CORE-000` §III.1,3–6, `FEAT-CORE-000` §II–V, and `DOM-LED-001` — specifically `INV-LED-009` (Atomic Seat Settlement), `INV-LED-015` (Seat Balance Serialization), and the multi-seat ascending-lock rule stated in `DOM-LED-001` §VII immediately after `INV-LED-017`'s closed-vocabulary table.

---

## IV. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/FEATURE-EXECUTION/FEAT-LED-001_POST_LEDGER_TRANSACTION.md`
- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md`
- `docs/SPEC/SPEC-ECON-001` (savings-interest cadence and posted-balance pricing; referenced for the §VII.2 obligation below, not restated here)

---

## V. Execution Context

### 1. Required Inputs

None. An optional `limit` bounds how many contexts one invocation processes (`scripts/settle_pending_transactions.py`'s standalone CLI use).

### 2. Resolved Context

The distinct `(seat_id, class_id)` pairs carrying `Transaction.posting_state == PENDING`, with `class_id` and `seat_id` both non-null, materialized before iterating (each context commits independently, which would otherwise invalidate a server-side cursor on PostgreSQL).

---

## VI. Orchestration Logic

### 1. Enumeration (Read-Only)

Query the distinct pending contexts and materialize them as a plain list before any mutation begins.

### 2. Per-Context Mutation (Atomic Transaction, Isolated)

For each context, open its own `FEAT-LED-003` boundary keyed `settlement-sweep:{class_id}:{seat_id}` and invoke `settle_balances(seat_id, class_id)`:

1. Acquire the exclusive seat lock, then the scoped `ClassEconomy` lock (`INV-LED-015`: seat row first, then class row, deterministic and unconditional — a settlement credit still takes the seat lock even though it never debits).
2. Lock every `PENDING` `Transaction` row for the context, ordered by account type then posting sequence.
3. Lock (or create) each account type's `LedgerBalanceSnapshot` row.
4. Advance `reconciled_through_posting_sequence` to the highest posting sequence now admitted, recompute `posted_balance_cents` from history through that cursor (`INV-LED-008`), and stamp `posted_at` on each newly admitted transaction.
5. Commit the context's boundary. Invoke the sweep only at top level, with no FEAT active. A nested invocation is rejected when `FEATContext` is constructed (its hard nesting guard, INV-ARC-000 §VIII.2 / INV-ARC-021 §V.2), so each pending context would be reported as failed rather than nested as a savepoint. `run_savings_interest_job` calls the sweep before opening its own payout FEAT for exactly this reason.

A context with no eligible transactions (already settled, or raced to settlement by a concurrent sweep) is a no-op.

### 3. Failure Isolation and Reporting

An exception from any single context's boundary is caught, logged without PII (seat/class log references only, never names), and recorded — both as a count and as the exact `(seat_id, class_id)` identity — in this FEAT's result. The sweep proceeds to the next context; one context's failure never aborts or rolls back another's settlement.

The result MUST name the failed contexts' identities, not only their count, as `failed_seat_class_pairs`. A downstream consumer that must not finalize a decision against a context's stale (pre-this-run) posted balance needs to know exactly which contexts to exclude (§VII.2).

---

## VII. Invariants & Constraints

1. **Seat-then-class lock order (`INV-LED-015`).** Every settlement for a context acquires the seat lock before the class lock, before pending rows and snapshots, in that deterministic order, without exception.

2. **Whole-roster callers must lock ascending before any class-scoped work.** `DOM-LED-001` §VII's multi-seat rule — acquire every affected seat anchor, in ascending seat-ID order, before acquiring any `ClassEconomy` lock or applying any class-scoped effect — binds every FEAT that batches a whole class's roster into one transaction, not only Ledger's own multi-seat commands. A foreign-key reference to a seat or to `classes.class_id` on an inserted row (e.g. `ObligationAssessment`) takes an implicit `FOR KEY SHARE` lock on the referenced row the instant it is inserted; a whole-roster FEAT that processes its roster seat-by-seat, inserting as it goes, pins the class row's `KEY SHARE` lock on its very first insert — well before every later roster seat is touched — which is `class-first` relative to those seats, the inverse of this FEAT's own seat-then-class order. A concurrent `FEAT-LED-003` context already holding a later roster seat `FOR UPDATE`, and waiting on the class row the roster FEAT now holds, forms the exact circular wait Postgres's deadlock detector reports. `FEAT-OBL-002` (rent reconciliation) violated this rule in production (#1640, closed by locking its complete roster via `lock_ledger_seats` before any assessment, late-fee, or perk-grant insert) and is the normative example other whole-roster FEATs must follow, not re-derive independently.

3. **A failed context's stale balance is not authority for a downstream finalization.** A caller that prices or finalizes state from "the posted balance as of this run" (the Savings Interest job, `FEAT-LED-001`, is the one caller today) MUST exclude any context named in `failed_seat_class_pairs` from that run's pricing, rather than treat this run's incomplete settlement as if it were complete. It MUST retry that context on a later, successful run rather than lose it: `FEAT-LED-001`'s payout idempotency key is scoped per `(class_id, seat_id, payout window)`, never per run, so skipping a context here costs nothing — the window stays open until a run that actually settles the context prices it. Writing a payout off the stale balance instead would be wrong permanently, since that window's idempotency key, once consumed, admits no correction.

4. **Idempotent.** A re-run processes only contexts still carrying `PENDING` activity; an already-settled context is a no-op (`INV-LED-004`).

5. **Isolation.** One context's failure, caught per §VI.3, never rolls back or blocks another context's settlement in the same sweep.

---

## VIII. Audit Requirements

The sweep's own log record (not a `DOM-OPS` audit event — this FEAT reconciles existing accepted effects rather than authoring a new business fact) MUST contain, without PII:

- `settled_contexts`: count of contexts this run admitted.
- `failed_contexts`: count of contexts this run could not settle.
- `failed_seat_class_pairs`: the exact `(seat_id, class_id)` identity of every failed context (log references only — `seat_log_ref` / `class_log_ref` — never a name).

---

## IX. Change Notes

**1.0 (2026-11-24)** establishes this contract. Names the production deadlock this closes (#1640): `FEAT-OBL-002`'s whole-class roster batch inserted its roster's `ObligationAssessment` rows seat-by-seat, implicitly pinning a `FOR KEY SHARE` lock on the class row from its first insert — well before a later roster seat already held `FOR UPDATE` by a concurrent `FEAT-LED-003` context — the circular wait Postgres reported in production. Fixed by extending `DOM-LED-001` §VII's multi-seat ascending-lock rule, until now applied only within Ledger's own multi-seat commands, to bind every whole-roster FEAT (§VII.2). Also closes the paired defect in the same incident: `run_savings_interest_job` had no visibility into which contexts a sweep it triggered could not settle, so it priced and permanently finalized at least one payout window off a stale, pre-failure balance. This FEAT's result now names the failed contexts explicitly (`failed_seat_class_pairs`, not only a count), and `FEAT-LED-001` excludes them from the run that observed the failure (§VII.3).

---

## X. Amendment

Increment the version and effective date, identify superseded rules, and preserve the governing `INV-LED-009`, `INV-LED-015`, and `DOM-LED-001` §VII authority. A change to the multi-seat ascending-lock rule's scope or to the per-window idempotency guarantee §VII.3 relies on requires amending `DOM-LED-001` and `FEAT-LED-001` respectively, not only this document.
