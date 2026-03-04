---
title: Insurance Claims and Coverage
category: features
subcategory: teacher-bills
roles: [teacher]
description: Review claims, approve coverage, and resolve issues.
keywords: [insurance, claims, coverage]
related:
  - user-guides/features/teacher/bills/insurance-policies
  - user-guides/diagnostics/teacher-rent-insurance
---

# Insurance Claims and Coverage

## Overview
The Insurance Management page allows you to review incoming student claims, approve coverage payouts, and resolve policy issues. Processing claims varies by claim type.

## Step-by-Step Instructions

### Reviewing and Approving Claims

1. Navigate to **Bills > Insurance** in the teacher sidebar.
2. Open the **Claims** tab to see pending claims.
3. Click on a specific claim to view the details.
4. Review the claim based on your policy rules:
   - **Transaction-Linked:** System shows the linked transaction. Amount is automatic—just approve/deny.
   - **Non-Monetary:** Student describes their claim. You decide the payout amount.
   - **Custom Monetary:** Student requests an amount. You approve, deny, or adjust.
5. Make your decision:
   - **Approve:** Funds automatically deposit to student's checking account
   - **Deny:** Explain why in the rejection reason field
6. Approving a claim marks it as **Paid** and creates a transaction record.

### Understanding Claim Displays

**For Transaction-Linked Claims:**
- Shows the original transaction (date, amount, description)
- Reimbursement amount is **auto-calculated** from transaction
- You cannot override the amount (ensures objectivity)
- Look for the "Linked Transaction" section

**For Non-Monetary Claims:**
- Shows student's description and incident date
- You enter the approval amount on approval
- Use judgment based on your policy limits
- Example: Policy says "up to $10" but student lost expensive item—you decide if it qualifies

**For Custom Monetary Claims:**
- Shows student's requested amount
- You can approve as-is or adjust the amount
- More administrative work but complete flexibility

## Important Notes

> [!NOTE]
> **Waiting periods:** Claims are strictly governed by the waiting period you configured for the policy. If a student complains they cannot submit a claim, verify that enough time has passed since their enrollment date.

> [!IMPORTANT]
> **Transaction-Linked Restrictions:** System automatically rejects transaction-linked claims if:
> - Transaction was voided/refunded
> - Transaction is a rent payment, insurance premium, or another insurance reimbursement
> - Transaction is an internal transfer (deposit/withdrawal)
> - Another claim already exists for that transaction
> - Student's premium payments are not current
> Check the rejection reason field for details.

> [!TIP]
> **Non-Monetary Claims Tip:** Set clear descriptions in your policy about what qualifies (e.g., "Lost school supplies only, not personal items"). This helps students self-assess and you process faster.

## Workflow Examples

### Transaction-Linked Example
1. Student submits claim: "I was charged twice for supplies"
2. You click claim and see:
   - Linked transaction: "Store Purchase - Supplies - $12.50"
   - Reimbursement amount: $12.50 (auto-calculated)
3. You verify:
   - Transaction date is within claim deadline? ✓
   - This is an eligible transaction type? ✓
   - No duplicate claims on this transaction? ✓
4. Click **Approve** → $12.50 automatically deposits to student

### Non-Monetary Example
1. Student submits claim: "I lost my calculator"
2. You click claim and see:
   - Description: "Calculator"
   - Policy limit: Up to $10 per claim
   - Incident date: Today
3. You verify:
   - Waiting period passed? ✓
   - This is eligible (school supplies)? ✓
   - Within monthly claim limit? ✓
4. Click **Approve** and enter: **$8** (reasonable replacement cost)
5. $8 automatically deposits to student

## Related guides
- [Insurance Policies](insurance-policies.md) - Creating and configuring policies
- [Teacher Rent and Insurance Diagnostics](../../../diagnostics/teacher/rent-insurance.md) - Troubleshooting claim issues
- [Student Insurance Coverage](../../student/bills/insurance-coverage.md) - Student perspective on claims
