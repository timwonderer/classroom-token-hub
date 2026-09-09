---
title: Insurance Policies
category: features
subcategory: teacher-bills
roles: [teacher]
description: Build an insurance policy, choose its type, group it into tiers, and understand why editing one publishes a new version rather than changing the old.
keywords: [insurance, policies, premium, versioning, immutable, tier group, transaction, productivity, non-monetary, hide, retire]
related:
  - user-guides/features/teacher/bills/insurance-enrollment
  - user-guides/features/teacher/bills/insurance-claims
  - user-guides/diagnostics/teacher/rent-insurance
---

# Insurance Policies

## Overview

A policy is a contract template. Students buy from it; what they buy is frozen at the moment of purchase. That is why the app never lets you change a policy in place — **every save creates a new version with a new identity**, and the old one carries on unchanged for everyone already holding it.

**Bills > Insurance** lists what you have built. The list shows policies that are for sale and policies you have hidden; retired ones drop off it entirely.

## Step-by-step instructions

### Creating a policy

1. Choose **New policy** on **Bills > Insurance**. You build the whole contract in one pass — there is no draft state.
2. Give it a **Policy Title** and an optional **Description**. Students see both.
3. Choose an **Insurance Type**. This decides which of the remaining fields you are asked for.
4. Set the **Premium** and a **Charge Frequency** of **Weekly** or **Monthly**.
5. Fill in the type-specific fields (see below).
6. Optionally put the policy in a tier group.
7. Choose **Create policy**.

### Choosing a type

The type is the biggest decision on the form, because it changes both what the policy covers and what you are allowed to configure.

| Field | Transaction | Productivity | Non-monetary |
| --- | --- | --- | --- |
| Reimbursement % | ● | ● | — |
| Payout Multiple | ● | ● | — |
| Claims / week-equiv. | ● | — | ● |
| Claim Window (days) | ● | — | — |
| Claimable dates / week-equiv. | — | ● | — |
| Waiting Period (days) | — | — | ● |

Fields that do not apply are hidden as you switch types, and they are not submitted at all — so switching type on an existing policy discards the terms that belonged to the old type.

**Claim Window** is the deadline students face: how many days after an incident they may still file. **Claims / week-equiv.** and **Claimable dates / week-equiv.** are the usage caps.

### Tier groups

Turn on **Part of a tier group** to offer students a choice of plans rather than a single product.

- A group holds up to three plans: **Basic**, **Mid**, and **Premium**.
- A student may hold only one plan per group.
- Each rank can be filled once. The **Tier** dropdown greys out ranks a group has already taken.

Pick an existing group from the dropdown or choose **＋ New group…** and name it.

### Editing a policy

Selecting a policy from the list opens the same form, prefilled, with the button relabelled **Save as new version**. That label is literal:

- A **new policy** is written, with its own identifier and your edited terms. It takes over the old one's place on the shelf — same state, and for a grouped policy the same rank.
- The **old policy is retired**. It stops being purchasable, but it stays readable, because it is still the contract for everyone who bought it.

So an edit is one action, not two: the revision goes on sale and the version it replaced comes off, together. Students only ever see one version of the product for sale.

Grouped policies edit exactly the same way. The original vacates its rank as the revision takes it, so there is nothing to retire by hand first.

### Withdrawing a policy

Each row carries **Hide** and **Retire**. Both stop new purchases and neither touches anyone's existing coverage. [Insurance Coverage and Enrollment](insurance-enrollment.md) covers what those states mean for policyholders.

A hidden policy also carries **Put back on sale**. Hiding is not reversible in the literal sense — a policy row never changes back — so this writes a new policy carrying the hidden one's exact terms and retires the hidden one. The result is the product back on the shelf on the terms you hid it with. Retired policies have no such control; retiring is final.

## Important notes

> [!WARNING]
> **An edit retires the version you edited, and retiring is permanent.** You cannot go back to the previous terms by undoing the edit — the old policy is closed to new purchases for good. To return to them you would build them again as a new policy. Read your changes back before saving.

> [!IMPORTANT]
> **Waiting Period delays when a policyholder can claim.** On a non-monetary policy, coverage becomes claimable at the start of the class day *N* days after purchase — a seven-day wait bought on a Monday opens the following Monday. A claim filed earlier is refused. Set it to zero if you want coverage effective immediately. Switching tiers within a group is a new purchase, so the new plan's wait starts over.

> [!IMPORTANT]
> **Terms are frozen at purchase.** A new version changes what *future* buyers get. Everyone holding the old version keeps the terms they bought until their coverage period ends. This is the lesson the feature exists to teach, and it is why there is no in-place edit.

> [!NOTE]
> **Values outside the recommended range are allowed.** The Economic Engine's suggestions are advisory. Only hard limits are enforced — premium at or above zero, reimbursement at or below 100%, no negative terms.

> [!TIP]
> Because each revision closes the version before it, it is worth getting a policy right before you announce it. Build it, buy nothing, read it back on the list, and only then tell students it exists.

## Related guides

- [Insurance Coverage and Enrollment](insurance-enrollment.md)
- [Insurance Claims](insurance-claims.md)
- [Rent and Insurance Troubleshooting](../../../diagnostics/teacher/rent-insurance.md)
