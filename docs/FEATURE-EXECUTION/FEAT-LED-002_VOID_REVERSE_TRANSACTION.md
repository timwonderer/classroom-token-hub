# FEAT-LED-002: Reversal of Monetary Transaction

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-LED-002 | 2.0 | 2026-09-07 | 1.1 | Normative |

---

## I. Purpose

This FEAT is a **Core Orchestrator** for reversing a previous monetary operation. It is governed by `SPEC-OPS-001`: money is reversed, grants are voided, and obligation-related facts permit neither. The original transaction remains historical fact; the correction is a new compensating monetary transaction.

The original transaction remains immutable. Voiding is represented by a new compensating ledger fact rather than mutation of the original row.

---

## II. Execution Context

### 1. Required Inputs
* `original_transaction_id`: The ID of the transaction to be reversed.
* `reason`: Enum explaining the reversal (e.g., `ADMIN_CORRECTION`, `PURCHASE_CANCELLED`).
* `idempotency_key`: Unique request identifier.

### 2. Resolved Context (MANDATORY)
* `original_transaction`: The authoritative record from `DOM-LED`.
* `seat_id`, `class_id`: Derived from the original transaction.
* `correlation_id`: **MUST** inherit or extend the `correlation_id` of the original operation.

---

## III. Orchestration Logic

### 1. Verification Phase (Read-Only)
1. **State Validation**: Verify that the `original_transaction`:
    * Exists in `DOM-LED`.
    * Has not already been compensated by a later reversal transaction.
    * Is not itself a terminal compensating transaction.
2. **Authorization Guard**: Call `DOM-OPS.check_reversal_authorization(actor_id, original_transaction_id)`.
3. **Linked State Identification**: Identify any downstream effects that must be reversed (e.g., linked `Entitlements` in `DOM-STORE` or `Obligation` status in `DOM-OBL`).

### 2. Mutation Phase (Atomic Transaction)
1. **Ledger Reversal**:
    * Call `FEAT-LED-001` (Post Ledger Transaction) with:
        * `from_account`: The `to_account` of the original.
        * `to_account`: The `from_account` of the original.
        * `amount_cents`: The exact `amount_cents` of the original.
        * `transaction_type`: `REVERSAL` (never `VOID`).
        * `description`: `Reversal of [original_id]: [reason]`.
        * `correlation_id`: The current extended correlation chain.
2. **Audit Finalization**:
    * Record the compensation as a new immutable ledger transaction linked through `correlation_id` and transaction type.
3. **Linked State Reversal**:
    * If linked to an `Entitlement`: Call `DOM-STORE` to set `status = REVOKED`.
    * If linked to an `Obligation`: Call `DOM-OBL` to set `status = VOIDED`.
4. **Audit Trace**:
    * Emit `ACT-MONY-003` via `DOM-OPS`.

---

## IV. Invariants & Constraints

1. **Exact Reversal**: A reversal MUST counteract the exact integer amount of the original. Partial corrections require a separately authorized correction operation; they are not represented as a transaction void.
2. **Chain Integrity**: The original transaction record is permanent; it MUST NOT be updated to represent the reversal.
3. **No Double-Reversal**: Idempotency MUST ensure that multiple reversal requests for the same transaction result in only one compensating reversal.

---

## V. Audit Requirements

The `DOM-OPS` audit log MUST contain:
* `original_transaction_id`
* `reversal_transaction_id`
* `reason`
* `correlation_id`
* `outcome`: (SUCCESS | ALREADY_REVERSED | UNAUTHORIZED)

---

## VI. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md`
