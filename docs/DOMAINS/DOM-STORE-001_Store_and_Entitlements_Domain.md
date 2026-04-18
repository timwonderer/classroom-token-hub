# Store and Entitlements Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-STORE-001 | 1.0 | 2026-04-18 | N/A | Normative |

## I. Purpose

Define the Store domain as the authority over store inventory, student-held items, entitlement lifecycle, and redemption history.

## II. Scope

This domain owns store catalog rows, visibility mappings, purchased/granted items, collective-goal item state, and redemption audit history.

## III. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`

## IV. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `store_items`
- `store_item_blocks`
- `student_items`
- `redemption_audit_logs`

It does not own money movement. Ledger owns transaction creation and reversal.

## V. Owned Tables

### `store_items`
- Catalog definitions, pricing, item behavior, collective-goal setup, and rent-linked flags.

### `store_item_blocks`
- Block visibility mapping for store items.

### `student_items`
- Purchased or granted student-held entitlements and use lifecycle.

### `redemption_audit_logs`
- Historical request/approval/rejection audit rows for redemptions.

## VI. Schema Contract

### `store_items`
- Key fields:
  - `teacher_id`
  - `join_code`
  - `class_id`
  - `name`
  - `price`
  - `item_type`
  - `inventory`
  - `is_active`
  - `collective_goal_instance_code`
  - `is_rent_linked`

### `store_item_blocks`
- Key fields:
  - `store_item_id`
  - `block`
  - `join_code`

### `student_items`
- Key fields:
  - `student_id`
  - `store_item_id`
  - `join_code`
  - `status`
  - `purchase_transaction_id`
  - `quantity_purchased`
  - `uses_remaining`
  - `collective_goal_instance_code`

### `redemption_audit_logs`
- Key fields:
  - `student_item_id`
  - `teacher_id`
  - `join_code`
  - `action`
  - `timestamp`
  - `source`

## VII. Constraints

- Store does not create or mutate ledger truth directly.
- Entitlement issuance/use/expiry history must be preserved once committed.
- Collective-goal progress is instance-scoped.
- Redemptions may change entitlement state and audit history, but not bypass Ledger for money effects.

## VIII. Derived / Cross-Domain Rules

- Purchases are orchestrated through FEAT: Store owns entitlement state, Ledger owns money state.
- Rent-linked store items remain Store-owned artifacts even when triggered by another workflow.

## IX. Amendment

Revisions require version increment, effective-date update, and continued consistency with higher-order invariants.
