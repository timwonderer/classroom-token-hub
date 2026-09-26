---
title: Insurance Claims
category: features
subcategory: teacher-bills
roles: [teacher]
description: How students file insurance claims and what the claim review screen shows you.
keywords: [insurance, claims, approve claim, reject claim, waiting period, claim caps, payout]
related:
  - user-guides/features/teacher/bills/insurance-policies
  - user-guides/diagnostics/teacher/rent-insurance
---

# Insurance Claims

## Overview

A claim is a student asking you to honour the policy they bought. They file it from their side; you decide what it is worth.

The review screen gathers everything you need to make that call in one place: what happened, what the contract they purchased actually promised, how many claims they have already made, and whether this one satisfies the policy's rules.

## Step-by-step instructions

### How a claim reaches you

Students file from their own insurance page against a policy they hold. You do not create claims. Filed claims appear in the **Filed claims** list on **Insurance Management**; select one to open its review screen.

### Reading the review screen

**Claim Details** covers the incident:

| Field | What it tells you |
| --- | --- |
| Student | Who filed |
| Insurance Policy | The product they hold |
| Claim Type | Transaction-based, Non-monetary, or Custom |
| Incident Date | When the thing happened |
| Filed Date | When they submitted |
| Linked Transaction | For transaction claims, the exact ledger entry with its amount |
| Claim Amount | What they are asking for |
| Current Status | Pending, Approved, Rejected, or Paid |

Below that you get the student's **Claim Description** and any **Student Comments**.

**Policy Information** shows the contract as it was sold to that student:

| Field | Why it matters |
| --- | --- |
| Claim Type | Which kind of policy the claim is against |
| Coverage Start | When the student's coverage began, or *Still in waiting period* |
| Waiting Period | How many days after purchase coverage takes effect |
| Filing Window | How many days from the covered transaction they had to file, with whether this claim made it |
| Reimbursement | The share of the loss the policy pays back |
| Period Allowance | How many claims (or claimable dates) they have used in the coverage period this claim was filed in |
| Period Payout Capacity | How much payout is left in that coverage period |

**Validation Status** does the arithmetic for you. It either lists the specific rules the claim breaks, or reads **Claim meets all requirements**.

**Student's Claims History** counts their pending, approved, rejected, and paid claims on this policy, and how many of their allowance they have used.

### Deciding

In **Process This Claim**:

1. Set the **Status**.
2. For transaction-based claims, enter the **Approved Amount**. Per-claim and period caps are applied automatically, so you cannot accidentally overpay.
3. If you are rejecting, fill in the **Rejection Reason** — it is required, and the student sees it.
4. Add **Teacher Notes** if you want a record for yourself.
5. Submit.

Approving a monetary claim deposits the approved amount into the student's checking account.

## Important notes

> [!IMPORTANT]
> **The contract is frozen at purchase.** Waiting periods, caps, and limits shown here are the ones in force when that student bought the policy. Editing the policy afterwards does not change their terms. If a student's numbers look different from your current settings, that is why.

> [!NOTE]
> **A claim is judged as of when it was filed.** Students cannot file while their coverage is paused for an unpaid premium, so any claim that reaches you was filed while they were covered. It stays reviewable even if their coverage pauses or ends afterwards. Allowances and payout caps count per coverage period — the one the claim was filed in.

> [!NOTE]
> **Check the waiting period first.** A student complaining they cannot claim has usually not reached their coverage start date. The screen tells you outright.

> [!TIP]
> Write the rejection reason for the student, not for your records. It is the only explanation they get, and a specific one ("filed 12 days after the incident; policy allows 7") teaches something. Use Teacher Notes for anything you would not want them to read.

## Related guides

- [Insurance Policies](insurance-policies.md)
- [Insurance Coverage and Enrollment](insurance-enrollment.md)
- [Rent and Insurance Troubleshooting](../../../diagnostics/teacher/rent-insurance.md)
