# Insurance Mechanics and Workflow

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| FEAT-INS-001 | 1.0 | 2026-03-15 | N/A | Normative |

**Feature:** Insurance System v2
**Date:** 2026-03-15
**Status:** Active specification

---

## Overview

This document defines the official mechanical rules for the Classroom Token Hub insurance system.

Insurance in CTH is a structured economic feature, not a freeform narrative tool. Teachers define the policy story presented to students, but the platform controls the economic mechanics so premiums, claim calculations, caps, and claim handling remain coherent across classrooms.

All economic calculations begin in weekly canonical units.

If a billing period is longer than one week, period-level values scale by the number of weeks in that period.

---

## Core Principles

1. The platform defines insurance mechanics, not the teacher-facing narrative.
2. Teachers control title, description, marketing badge, repurchase logic, filing time limit, and bundle discount.
3. Product type determines how claims are filed, reviewed, and reimbursed.
4. Tier groups define protection levels of the same insurance concept.
5. Weekly CWI is the base unit for preset economic calculations.
6. Economic policy affects only variable monetary premium recommendations.
7. Claim calculations must be deterministic and auditable.

---

## Creation Workflow

Insurance creation follows this ordered workflow:

1. Select creation mode.
2. Select product type.
3. Optionally configure a tier group.
4. Review or enter economic parameters.
5. Enter title, description, and marketing badge.
6. Configure repurchase logic and bundle discount.

This workflow applies in both teacher-facing UI and any backend validation path.

---

## Creation Modes

### Preset Mode

Preset mode uses system-calculated economic mechanics.

Teacher-configurable fields:

- product type
- optional tier group
- title
- description
- marketing badge
- repurchase logic
- filing time limit
- bundle discount
- billing period

System-computed fields:

- premium
- waiting period
- coverage percent for transaction-linked policies
- payout caps
- claim-count caps where defined by the preset rules

Teachers may review computed values in preset mode but must not override them except where this spec explicitly requires teacher-entered envelope values for preset variable monetary products.

### Custom Mode

Custom mode allows the teacher to select a product type and optional tier configuration, then fill in the product-specific economic fields directly.

System invariants still apply in custom mode.

---

## Product Types

CTH supports three insurance product types:

1. Non-Monetary
2. Transaction-Linked Monetary
3. Variable Monetary

Each product may optionally belong to a tier group.

### Canonical Product Mapping

Implementation layers may contain legacy internal names. The canonical product names are:

- `non_monetary` -> Non-Monetary
- `transaction_monetary` -> Transaction-Linked Monetary
- `legacy_monetary` -> Variable Monetary

---

## Non-Monetary Insurance

Non-monetary claims do not create ledger reimbursements.

These claims represent teacher-reviewed events resolved outside the money ledger, such as privileges, deadline forgiveness, or special permissions.

### Preset Defaults

| Attribute | Not Tiered | Basic | Mid | Premium |
|---|---|---|---|---|
| Premium | weekly_CWI x 0.05 | weekly_CWI x 0.03 | weekly_CWI x 0.05 | weekly_CWI x 0.07 |
| Claim Cap per Period | 2 | 1 | 2 | 3 |
| Waiting Period | 5 days | 7 days | 5 days | 3 days |
| Coverage Period | Teacher selected | Teacher selected | Teacher selected | Teacher selected |

### Custom Mode Rules

Teachers may set:

- premium
- claim cap per period
- waiting period
- coverage period

Non-monetary policies never set:

- coverage percent
- per-claim reimbursement amount
- reimbursement ledger transactions

---

## Transaction-Linked Monetary Insurance

Transaction-linked policies reimburse part of a posted ledger transaction.

Students must choose a qualifying transaction, and the system calculates payout automatically.

### Claim Calculation

```python
transaction_loss = abs(transaction.amount)

payout = min(
    transaction_loss * coverage_percent,
    remaining_period_cap
)
```

### Preset Defaults

| Attribute | Not Tiered | Basic | Mid | Premium |
|---|---|---|---|---|
| Coverage Percent | 0.70 | 0.50 | 0.70 | 0.90 |
| Waiting Period | 5 days | 7 days | 5 days | 3 days |
| Premium | weekly_CWI x 0.08 | weekly_CWI x 0.05 | weekly_CWI x 0.08 | weekly_CWI x 0.11 |
| Weekly Cap | premium x 3 | premium x 2 | premium x 3 | premium x 4 |
| Period Cap | weekly_cap x weeks_in_billing_period | same | same | same |

### Custom Mode Rules

Teachers may set:

- premium
- waiting period
- coverage percent
- weekly cap

The system must derive:

- period cap from weekly cap and billing period length

Transaction-linked policies must never accept manual claim amounts from students.

---

## Variable Monetary Insurance

Variable monetary insurance allows students to submit a claim amount for teacher review.

These products behave like teacher-reviewed underwriting with a bounded liability envelope.

### Base Risk Envelope

Teacher-entered fields:

- max payout per claim
- max claims per coverage period
- max payout per period
- waiting period

### Exposure Calculation

```python
liability = min(
    max_payout_per_period,
    max_claims * max_payout_per_claim
)
```

### Premium Recommendation

```python
recommended_premium = liability * risk_factor
```

### Economic Policy Risk Factors

| Economic Policy | Risk Factor |
|---|---|
| Tight | 0.20 |
| Default | 0.15 |
| Comfortable | 0.12 |

### Tier Scaling

If a tier group is present, scale the base exposure values as follows:

| Tier | Exposure Scale | Waiting Period |
|---|---|---|
| Basic | x1.0 | 7 days |
| Mid | x1.5 | 5 days |
| Premium | x2.0 | 3 days |

Scaled values apply to:

- max payout per claim
- max claims
- max payout per period

Preset mode for variable monetary products uses the teacher-entered liability envelope, then computes the recommended premium from the scaled liability.

---

## Tier Groups

Tier groups model multiple protection levels of the same insurance concept.

Examples include a basic, mid, and premium version of one protection category.

### Tier Invariants

1. All policies in a tier group must share the same product type.
2. Each tier may appear only once inside a tier group.
3. Students may hold only one active policy from the same tier group.

### Tier Labels

Canonical tier labels:

- Basic
- Mid
- Premium

---

## Universal Teacher-Controlled Settings

The following settings remain configurable regardless of product type or creation mode:

- title
- description
- marketing badge
- repurchase logic
- filing time limit
- bundle discount

These fields must remain available in both preset mode and custom mode.

---

## Repurchase Logic

Repurchase logic controls how students may re-enroll after cancellation.

### Supported Rules

| Rule | Description |
|---|---|
| Cycle Locked | Enrollment is only allowed at the start of a billing cycle |
| Cooldown | Student must wait a configured number of days before repurchasing |
| Continuous | Policy renews unless cancelled |

Implementation may use internal flags to represent these rules, but the product-facing behavior must match the table above.

---

## Claim Eligibility Rules

Transaction-linked claims must satisfy all of the following:

- amount < 0
- status = POSTED
- transaction not voided
- transaction not previously claimed
- transaction owned by the claimant

### Hard Exclusions

The following categories are never insurable:

- insurance_premium
- insurance_reimbursement
- internal_transfer
- interest

### Optional Exclusions

Teacher policy may additionally exclude:

- rent
- privilege purchases
- store purchases
- hall passes
- specific tier of store items
- fines
- collective goal contributions

Optional exclusions may narrow eligibility further, but never override the hard exclusions.

---

## Economic Scaling

All preset insurance calculations begin in weekly units.

### Period Conversion

| Period | Weeks |
|---|---|
| Weekly | 1 |
| Biweekly | 2 |
| Monthly | 4 |

```python
period_value = weekly_value * weeks_in_period
```

### Scaling Constraints

- Coverage percentages do not scale by economic policy.
- Transaction-linked payout limits do not change with economic policy except through the selected preset rule itself.
- Economic policy only changes the premium recommendation for variable monetary insurance.

---

## System Guarantees

The insurance system must preserve the following guarantees:

- deterministic claim calculations
- frozen policy snapshots at enrollment
- join-code financial isolation
- single claim per transaction
- reimbursement deduplication

These guarantees protect accounting correctness and prevent cross-class or duplicate reimbursement exploits.

---

## Implementation Notes

The current implementation is expected to align to this document in:

- teacher insurance creation and edit flows
- student marketplace enrollment behavior
- student claim filing flows
- teacher claim processing flows
- snapshot and reimbursement logic

If the code and this document conflict, this document is authoritative for the insurance feature.
