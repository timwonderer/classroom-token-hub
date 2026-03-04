---
title: Insurance Policies
category: features
subcategory: teacher-bills
roles: [teacher]
description: Create, edit, and manage insurance policies.
keywords: [insurance, policies, premium, coverage]
related:
  - user-guides/features/teacher/bills/insurance-claims
  - user-guides/diagnostics/teacher-rent-insurance
---

# Insurance Policies

## Overview
Insurance policies act as automated deductions that grant students the right to submit financial claims for specific classroom events (like lost items or absences). This tool allows you to control premiums, coverage amounts, and claim rules.

## Claim Types Explained

When creating a policy, you must choose a **claim type** that determines how reimbursement amounts are calculated:

### 1. Transaction-Linked Reimbursement
**Use when:** You want automatic, objective reimbursement based on a specific transaction (e.g., accidental overcharge, refund request).

**How it works:**
- Student submits a claim referencing a transaction (e.g., "I was charged twice for supplies")
- System automatically calculates reimbursement from the linked transaction amount
- Teacher just needs to approve/deny (not enter an amount)
- More objective and prevents disputes over payout amounts

**Example:** Create an "Overcharge Protection" policy where students can claim refunds for duplicate charges. Amount is automatically calculated from the flagged transaction.

**What CAN'T be claimed:**
- ❌ Rent payments, insurance premiums, or other insurance reimbursements
- ❌ Internal transfers (deposits/withdrawals)
- ❌ Voided transactions
- ❌ Transactions belonging to other students (security check)
- ❌ Duplicate claims on the same transaction
- ❌ Already-reimbursed transactions

### 2. Non-Monetary Claims
**Use when:** Students are requesting compensation for something non-financial (e.g., "I lost a textbook" or "I missed a day of work").

**How it works:**
- Student describes what they're claiming (the item or event)
- Teacher reviews and decides payout amount
- Teacher must manually enter the approved amount
- More flexible for subjective situations

**Example:** "Lost Item Insurance" where students describe lost supplies. Teacher decides if it's covered and the payout amount.

### 3. Custom Monetary Reimbursement
**Use when:** You're using an older system or need complete flexibility with manual entry.

**How it works:**
- Student enters their own requested amount
- Teacher reviews and either approves, denies, or adjusts
- Teacher must manually enter the approved amount
- Most flexible but requires teacher judgment on every claim

**Example:** "Miscellaneous Coverage" where students can claim for various issues and request any amount.

---

## Step-by-Step Instructions

### Creating a New Policy

1. Navigate to **Bills > Insurance** in the teacher sidebar.
2. Click on **Add New Policy**.
3. **Choose your claim type** (this is the critical decision):
   - **Transaction-Linked**: For objective, transaction-based claims
   - **Non-Monetary**: For items/events without direct cost
   - **Custom Monetary**: For complete flexibility

4. Define the key fields:
   - **Policy Name:** Clear title (e.g., "Overcharge Protection", "Lost Item Insurance")
   - **Premium and frequency:** How much it costs per student and billing period
   - **Coverage amount** (for non-transaction types): Maximum payout per claim
   - **Waiting period:** Days after enrollment before students can file claims (e.g., 7 days)
   - **Maximum claims:** How many claims allowed per period (e.g., 2 per month)
   - **Claim filing deadline:** Days after incident to file (e.g., 30 days)

5. Save the policy to make it available for student enrollment.

### Managing Existing Policies

1. Navigate to **Bills > Insurance**.
2. Under the **Existing Policies** section, select a policy to edit its terms.
3. Use the **Active Student Policies** tab to manage who is currently enrolled.
4. Click on a policy to:
   - Change premium or frequency
   - Adjust waiting periods or claim limits
   - Deactivate if no longer using
   - Delete if never activated

## Important Configuration Notes

> [!IMPORTANT]
> **Claim Type is Final:** Choose your claim type carefully at creation. You cannot change it after students start enrolling.

> [!WARNING]
> **Transaction-Linked Restrictions:** If using transaction-linked claims, students can ONLY claim on eligible transaction types:
> - ✅ Store purchases, optional items, classroom fees
> - ❌ Rent, insurance premiums, transfers, voided transactions, or items already covered by other insurance

> [!TIP]
> **Waiting Periods Protect You:** Setting a 7-14 day waiting period prevents students from enrolling, paying, and immediately claiming. This ensures they're committed to the insurance.

## Common Policy Examples

### Example 1: Overcharge Protection (Transaction-Linked)
- **Claim Type:** Transaction-Linked Reimbursement
- **Premium:** $0.50 per month (cheap add-on)
- **Coverage:** Reimbursement amount = transaction amount
- **Waiting Period:** 7 days
- **Max Claims:** 3 per month
- **When used:** Student claims they were double-charged or overcharged

### Example 2: Lost Item Insurance (Non-Monetary)
- **Claim Type:** Non-Monetary
- **Premium:** $2.00 per month
- **Coverage Amount:** Up to $10 per claim
- **Waiting Period:** 0 days (immediate coverage)
- **Max Claims:** 2 per month
- **When used:** "I lost my pencil set" or "My notebook was damaged"

### Example 3: Absence Reimbursement (Non-Monetary)
- **Claim Type:** Non-Monetary
- **Premium:** $1.00 per month
- **Coverage Amount:** Up to $5 per day missed
- **Waiting Period:** 0 days
- **Max Claims:** 5 per month
- **When used:** Student missed class and wants compensation for lost work/payroll time

---

## Related guides
- [Insurance Claims and Coverage](insurance-claims.md) - Approving and processing claims
- [Teacher Rent and Insurance Diagnostics](../../../diagnostics/teacher/rent-insurance.md) - Troubleshooting
- [Student Insurance Coverage](../../student/bills/insurance-coverage.md) - Student perspective
