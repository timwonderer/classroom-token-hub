# FEAT-LED-006: Apply Teacher Penalty

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-LED-006 | 1.0 | 2026-11-04 | — | Normative |

---

## I. Purpose

This FEAT is the top-level orchestration identity for a teacher fining one or more students.

A fine is a teacher-authorized financial deduction (owner ruling 2026-11-04, issue #1701). It is a Ledger `penalty`: a direct checking debit that carries the teacher's reason, which the student sees in their transaction history. It is neither a purchase nor an obligation (`SPEC-ECON-003` §4.5.1.1).

## II. Scope

One teacher submission that fines one or more student seats of one class by the same amount for the same reason. Out of scope: a reusable fine catalog (there is none; `DOM-POL-001` v2.11), any obligation lifecycle (`DOM-OBL-001` §II.D), disciplinary records, and correction, which is an exact reversal under `FEAT-LED-002`.

## III. Authority Level

Normative; subordinate to `INV-CORE-000`, `FEAT-CORE-000` (one atomic FEAT context per top-level orchestration, no nested FEAT), `DOM-LED-001`, `DOM-CLASS-002` §VII and `SPEC-ECON-003` §4.5, §4.5.1.1 and §4.5.1.1A.

## IV. Dependencies

- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md` (INV-LED-017 `penalty`; seat-first lock order)
- `docs/FEATURE-EXECUTION/FEAT-LED-000_CANONICAL_MONETARY_RESOLUTION_WORKFLOW.md` (§XI.5 funding)
- `docs/FEATURE-EXECUTION/FEAT-LED-001_POST_LEDGER_TRANSACTION.md`
- `docs/FEATURE-EXECUTION/FEAT-LED-002_VOID_REVERSE_TRANSACTION.md` (correction)
- `docs/SPEC/SPEC-ECON-003_ECONOMIC_ENGINE_CALCULATION_AND_REFERENCE_SPECIFICATION.md` (§4.5 fine band; §4.5.1.1 penalties; §4.5.1.1A)

## V. Authority

Ledger owns the penalty transaction, any protection transfer that funds it, and the resulting balances. Class Configuration owns the overdraft-protection directive the FEAT reads and passes into Ledger resolution. The Economic Engine owns the advisory CWI fine band. This FEAT owns the orchestration: verifying the selection, comparing the confirmed outcome, and composing Ledger resolution and posting in one context. It writes no Obligations, Productivity or Policies state.

## VI. Required Context

- `class_id`, from the teacher's canonical context; the acting teacher seat is the actor.
- `seat_ids` — one or more student seats of `class_id`.
- `amount` — positive, in cents; the same for every seat.
- `reason` — required, at most 200 characters. The posted description is `Fine: <reason>`.
- `expected_preview_digest` — identity of the outcome the teacher confirmed: the student-visible text and each seat's amount, balances and funding.
- `idempotency_key` — the submission token minted when the teacher reviewed.
- `correlation_id`.

## VII. Orchestration Logic

### 1. Review (read-only)

Before anything posts, the teacher sees the requested deduction, the class's recommended fine range (`SPEC-ECON-003` §4.5: `CWI × fine_rate` over the class's economic mode), and, for each student, checking and savings before, any protection transfer, and checking and savings after. A range is shown only when the class has a CWI. An amount outside the range is warned about and may still be applied: the band is advisory, not an authorization limit. Review writes nothing (`INV-ARC-007`).

### 2. Verification

1. Every submitted student resolves to a student seat of `class_id`. Any that does not refuses the whole submission.
2. Lock every selected seat in ascending seat order (`lock_ledger_seats`).
3. Every seat must be claimed. An unclaimed seat takes part in no economic activity, so a selection that contains one is refused whole; it is never dropped silently.
4. Lock the ClassEconomy row, so concurrent submissions sharing a token serialize, then look up every reservation made under this token (§VIII.4).
5. Resolve each seat's plan under the class's banking directive (never a fee — `SPEC-ECON-003` §4.5.1.1), and compare the digest of the resolved outcome to `expected_preview_digest`. On any difference nothing posts and the teacher reviews the updated outcome.

### 3. Mutation

For each seat, `apply_resolved_ledger_plan` posts the funding legs, if any, and the `penalty` principal under the reservation `(class_id, FEAT-LED-006, penalty:<token>:<batch>:<seat_id>)`, where `<batch>` identifies the complete submission: every selected seat, the amount and the student-visible text. All seats commit in this one FEAT transaction or none do.

## VIII. Invariants

1. A penalty is one `ledger_transaction` row: `type = penalty`, `account_type = checking`, negative amount, `mechanism = teacher`, `actor_seat_id` the teacher seat, description `Fine: <reason>`.
2. Funding follows `SPEC-ECON-003` §4.5.1.1A: savings moves the exact checking shortfall only when protection is on and savings covers all of it; otherwise checking may go below zero. No partial sweep.
3. A penalty never generates an NSF or overdraft fee and never creates an obligation, assessment, deferred debt or waiver.
4. One submission token posts at most once, for the one batch it was reviewed for. A resubmitted token for the same batch returns what it posted and posts nothing; the token reused for any other selection (a subset, a superset or different students), amount or reason is refused and posts nothing. A second, deliberate fine with the same amount and reason is reviewed again, receives a new token, and posts.
5. A multi-student submission is all-or-nothing.
6. Posted penalties are never edited or deleted. Correction is an exact reversal under `FEAT-LED-002` that references the penalty by `original_transaction_id`; both entries remain in history.

## IX. Amendment

Increment the version and effective date, identify superseded rules, and preserve the governing INV and DOM hierarchy.

### Change Notes

**1.0 (2026-11-04, review)** binds each submission token to its complete batch (§VII.3, §VIII.4), serializes same-token submissions on the ClassEconomy lock, and adds the student-visible text to the confirmed-outcome digest. Contract version unchanged: these complete the 1.0 invariants before first release.

**1.0 (2026-11-04)** establishes `FEAT-LED-006` (owner ruling 2026-11-04, issue #1701): teacher fines are Ledger penalties, with no catalog and an advisory CWI band. Runtime: `app/feats/penalty_feat.py`, `app/services/ledger_penalty_service.py`, routes `admin.payroll_fine_review` and `admin.payroll_fine`, migration `a0faf8b2a35d`.
