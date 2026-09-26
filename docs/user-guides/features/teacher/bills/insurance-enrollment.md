---
title: Insurance Coverage and Enrollment
category: features
subcategory: teacher-bills
roles: [teacher]
description: How students take out coverage, why you cannot revoke it, and how to wind a policy down.
keywords: [insurance, enrollment, coverage, hide policy, retire policy, cancel coverage, contract]
related:
  - user-guides/features/teacher/bills/insurance-policies
  - user-guides/features/teacher/bills/insurance-claims
---

# Insurance Coverage and Enrollment

## Overview

You do not enroll students in insurance. Students buy it.

That distinction drives everything else on this page. A purchased policy is a contract between the student and the class, and the app treats it that way: you cannot cancel it, you cannot change its terms, and you cannot take it away. What you *can* do is stop selling it.

## Step-by-step instructions

### How students take out coverage

A student buys a policy from their own insurance page. At the moment of purchase the terms are frozen onto their contract — premium, charge frequency, claim time limit, and every cap.

Coverage starts at that moment, unless the policy carries a **Waiting Period** — then claims open *N* days later. Any policy type can have one. Either way an incident dated before the purchase is never covered.

### How coverage stays in force

After the first premium, each period's premium is billed a few days before the period starts and paid automatically from the student's checking. If the student cannot cover it, the premium stays owing and their coverage **pauses** when the new period starts: their card reads **Premium overdue** and claims are refused until they pay. They pay from their policy page; coverage returns from that moment on.

What happens if they never pay is set on the policy — keep billing, or cancel after a number of days. See [Recurring billing](insurance-policies.md#recurring-billing).

### Withdrawing a policy from sale

On **Bills > Insurance**, each policy in **Existing Policies** shows its state and two controls.

| State | Meaning |
| --- | --- |
| For sale | Students can buy it |
| Hidden — winding down | No new purchases; existing holders keep their coverage |
| Retired | Permanently unavailable for new enrollment |

- **Hide** stops new purchases while leaving current policyholders untouched. Use this when you want to phase a product out.
- **Retire** does the same thing permanently. You are asked to confirm.

Neither one touches anybody's existing coverage. Both are about the shelf, not the contracts already sold.

### How coverage actually ends

Coverage ends in one of two ways, and never by your hand:

- **The student cancels.** Their coverage runs to the end of the last period they are committed to — the current one, or next period if they already paid toward it — and then expires. An unpaid bill for next period is cancelled.
- **The policy cancels for nonpayment**, if it uses that rule. Coverage expires when the unpaid limit runs out.

Either way, premiums for periods that had already started stay owed, and paying them later does not restore the coverage. If you turn insurance off for the class, nothing new can be bought, but students who still owe a premium keep their insurance page so they can pay it.

There is no early termination, no refund, and no way for you to revoke a policy someone is holding.

## Important notes

> [!IMPORTANT]
> **Purchased policies are enforceable contracts.** Editing a policy changes what *future* buyers get. Everyone already holding it keeps the terms they bought until their coverage period ends. This is deliberate — it is the lesson the feature exists to teach.

> [!IMPORTANT]
> **A Waiting Period is enforced on every policy type.** Claims filed before it elapses are refused. Set it to zero for coverage that is claimable from purchase. See [Insurance Policies](insurance-policies.md).

> [!IMPORTANT]
> **Editing retires the version you edited.** The revision takes the original's place on the shelf and the original comes off, in one action — you do not hide or retire it yourself. [Insurance Policies](insurance-policies.md) covers this.

> [!IMPORTANT]
> **You cannot revoke a student's coverage.** Not for discipline, not for a policy change, not by hiding or retiring the product. If you need a consequence, use a different tool — insurance is not one of them.

> [!NOTE]
> **Hiding is reversible, retiring is not.** A hidden policy carries **Put back on sale**, which re-offers its exact terms. A retired policy is permanently unavailable for new enrollment. If you are unsure, hide it.

> [!NOTE]
> **There is no roster of who is covered.** The Insurance Management page lists your policies, not your policyholders. To check one student's coverage, ask them to show you their insurance page. A teacher-facing enrollment list is a known gap.

> [!TIP]
> If a claims dispute turns on when coverage started, the answer is the purchase date plus that student's own waiting period — not the terms currently shown in your settings. The student's insurance page carries the contract they actually bought.

## Related guides

- [Insurance Policies](insurance-policies.md)
- [Insurance Claims](insurance-claims.md)
