# FEAT-LED-002: Reversal of Monetary Transaction

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-LED-002 | 2.2 | 2026-10-03 | 2.1 | Normative |

---

## I. Purpose

This FEAT is a **Core Orchestrator** for resolving an eligible pre-use Store
purchase. It is governed by `SPEC-OPS-001` and supports two explicit outcomes:
`REVERSE` (money is reversed and active grants are revoked) and `REFUND` (money
is reversed while the active entitlement is retained). The original transaction
remains historical fact; the correction is a new terminal compensating monetary
transaction.

The original transaction remains immutable. Voiding is represented by a new compensating ledger fact rather than mutation of the original row.

---

## II. Scope

Exact whole monetary reversal and the existing eligible pre-use Store REVERSE/REFUND outcomes. Partial/residual payroll recovery requires its separately authorized business FEAT; this contract supplies no generic undo operation.

---

## III. Authority Level

Normative; subordinate to `INV-CORE-000` §III.1,3–6, `INV-CORE-001` §III, VIII, `INV-ARC-006` §V, `INV-ARC-009` §V, `INV-ARC-016` §V and `INV-ARC-021` §V, VII. `FEAT-CORE-000` §II–V requires one atomic context; Ledger owns all compensation and money state. This contract explicitly incorporates `SPEC-OPS-001` §III.3.8 and `SPEC-LED-002` §§III–VIII under `DOM-LED-001` §VII.1–1A.

---

## IV. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md`
- `docs/DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md`
- `docs/DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- `docs/DOMAIN/DOM-OBL-001_OBLIGATIONS_DOMAIN.md`
- `docs/SPEC/SPEC-OPS-001_REVERSAL_AND_VOID.md`
- `docs/SPEC/SPEC-LED-002_COMMAND_IDEMPOTENCY_RESERVATION_AND_ENFORCEMENT.md`

## V. Execution Context

### 1. Required Inputs
* `original_transaction_id`: The ID of the transaction to be reversed.
* `reason`: Enum explaining the reversal (e.g., `ADMIN_CORRECTION`, `PURCHASE_CANCELLED`).
* `idempotency_key`: Unique request identifier.

### 2. Resolved Context (MANDATORY)
* `original_transaction`: The authoritative record from `DOM-LED`.
* `seat_id`, `class_id`: Derived from the original transaction.
* `correlation_id`: **MUST** retain exactly the `correlation_id` of the original operation.

---

## VI. Orchestration Logic

### 1. Verification Phase (Read-Only)
1. **State Validation**: Verify that the `original_transaction`:
    * Exists in `DOM-LED`.
    * Has no prior attributable compensation of any kind, as queried by Ledger under `DOM-LED-001` §VII.1A; accepted pending compensation counts. Exact reversal cannot coexist with prior partial/residual recovery.
    * Is not itself a terminal compensating transaction.
2. **Authorization Guard**: Call `DOM-OPS.check_reversal_authorization(actor_id, original_transaction_id)` and resolve the explicit outcome (`REVERSE` or `REFUND`).
3. **Linked State Identification**: Resolve downstream Store entitlements through their owning-domain query. Any obligation-related monetary or grant provenance fails closed under `SPEC-OPS-001` §VII; it does not authorize reversal, void, or obligation status mutation.

### 2. Mutation Phase (Atomic Transaction)
1. **Ledger Reversal**:
    * Hold the scoped seat lock, then ClassEconomy, then original transaction lock, then pending rows/snapshots in deterministic order. Re-evaluate reversal eligibility and remaining recovery inside that transaction.
    * Invoke the Ledger posting domain command described by `FEAT-LED-001` inside this single FEAT context, never execute another FEAT, with:
        * For a single original effect, retain its account target and use signed integer `amount_cents = -original.amount_cents`. Do not invent source/destination accounts or a transfer for that effect.
        * If a separately authorized original operation is a genuine two-effect transfer, invert each matching signed leg on its original account target; preserve exact cents and the equal-and-opposite total. This posting shape does not itself grant transfer-reversal authority.
        * `transaction_type`: `REVERSAL` (never `VOID`).
        * `description`: `Reversal of [original_id]: [reason]`.
        * `correlation_id`: The original transaction correlation identity.
        * Permanent `(class_id, feat_code, idempotency_key)` reservation and Ledger-defined replay fingerprint/version.
        * For a payroll-credit reversal, original public Ledger locator, opaque reversal intent locator and `compensation_amount_cents` equal to the absolute recovery debit. These are mandatory so later partial/residual recovery sees the full recovery; funding transfer legs contribute zero.
2. **Audit Finalization**:
    * Record the compensation as a new immutable ledger transaction linked through `correlation_id` and transaction type.
3. **Linked State Resolution**:
    * For `REVERSE`, invoke the Store domain command to append `REVOKED` for eligible linked active entitlements; for `REFUND`, retain them under `SPEC-OPS-001` §3.1A.
    * Obligation provenance has already denied execution; no obligation void or status mutation is permitted.
4. **Audit Trace**:
    * Emit `ACT-MONY-003` via `DOM-OPS`.

---

## VII. Invariants & Constraints

1. **Exact Reversal**: A reversal or refund MUST counteract the exact integer amount of the original. Partial corrections require a separately authorized correction operation; they are not represented as a transaction void.
2. **Chain Integrity**: The original transaction record is permanent; it MUST NOT be updated to represent the reversal.
3. **No Double-Resolution**: Idempotency MUST ensure that multiple resolution requests for the same transaction result in only one terminal compensating transaction. A compensating transaction itself cannot be voided or reversed.
4. **Correlation Preservation**: The compensating transaction MUST use the original transaction's `correlation_id` and immutable `original_transaction_id`. Ledger derives reversal linkage through DOM-LED-001 §VII.0 and enforces one exact child even across distinct command keys. Neither pending nor posted reversal initializes an original-row pointer. The same lock and linkage rules apply to reversal of an original debit; positive-credit reversal additionally enforces §VII.1A compensation authority.

---

## VIII. Audit Requirements

The `DOM-OPS` audit log MUST contain:
* `original_transaction_id`
* `reversal_transaction_id`
* `reason`
* `correlation_id`
* `outcome`: (SUCCESS | ALREADY_REVERSED | UNAUTHORIZED)

---

## IX. Change Notes

**2.1 (2026-10-03)** supersedes 2.0's reversal-only prior-compensation check and nested FEAT call. Exact reversal is available only for uncompensated originals. Separately authorized partial/residual payroll correction belongs to `FEAT-PROD-003`/`FEAT-PROD-005`, uses proposed `payroll_correction` and is never REVERSAL or VOID. This document does not authorize partial Store refunds or change Store entitlement eligibility. Incorporates `SPEC-OPS-001` §III.3.8 and `SPEC-LED-002` §§III–VIII through `DOM-LED-001` §VII.1–1A.

## X. Amendment

Increment the version, effective date and supersedes fields and preserve exact reversal, terminality and the governing INV/DOM authority.
