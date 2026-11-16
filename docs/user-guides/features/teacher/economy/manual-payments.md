---
title: Manual Payments
category: features
subcategory: teacher-economy
roles: [teacher]
description: Pay selected students a one-time credit, or fine them, from the Payroll page.
keywords: [manual payment, credit, bonus, payroll, one-time payment, fine, penalty, deduction]
related:
  - user-guides/features/teacher/economy/payroll-run
  - user-guides/features/teacher/economy/payroll-settings
  - user-guides/features/teacher/bills/index
---

# Manual Payments

## Overview

A manual payment is a one-time credit you issue outside the regular payroll run — a bonus for helping a classmate, a make-good for a missed payday, a prize for a class competition. It lands in the student's **checking** account immediately.

Manual payments live on the **Payroll** page, under the **Manual Payments** tab. The same tab lets you **fine** students: take a set amount from their checking, with a reason they can see.

## Step-by-step instructions

### Issuing a credit

1. In the teacher sidebar, open **Economy**.
2. Select **Payroll**.
3. Select the **Manual Payments** tab.
4. In the **Select Students** panel on the left, check the box beside each student who should receive the credit. The checkbox in the table header selects everyone at once, and the banner below the table shows how many students you have selected. The table also shows each student's current checking and savings balance.
5. In the **Payment Details** panel on the right, fill in:

   | Field | What to enter |
   | --- | --- |
   | Description | A short note explaining the credit. It appears on the student's transaction history. |
   | Action | Fixed at **Manual Credit**. This panel only adds money. To take money away, use **Fine Students** below it. |
   | Amount | A positive dollar amount. |

6. Select **Apply Payment**.

Each selected student is credited the full amount — the amount is not split between them. A confirmation tells you how many students were paid.

### Fining students

1. On the **Manual Payments** tab, check the box beside each student you are fining, in the same **Select Students** panel.
2. In the **Fine Students** panel, fill in:

   | Field | What to enter |
   | --- | --- |
   | Reason | Why you are fining them. Students see it in their transaction history as **Fine: your reason**. |
   | Amount | A positive dollar amount. Each selected student is fined the full amount. |

   Below the amount you see the recommended fine range for your class. The range is a guide, not a limit.
3. Select **Review fine**. Nothing is taken yet.
4. Check the review page. It shows the amount, the recommended range (with a warning if your amount is outside it), and for each student their checking and savings now, anything moved from savings, and their balances after the fine.
5. Select **Apply fine** to fine every selected student, or **Cancel** to fine nobody.

What happens to the student's money:

- The fine comes out of **checking**.
- If you have overdraft protection on and the student's savings can cover the whole amount checking is short, that amount moves from savings first. If savings can't cover all of it, savings is left alone.
- Otherwise checking can go below zero. A fine never adds a fee and never becomes a bill.

To undo a fine, open the student's page and reverse the fine transaction. The fine and its reversal both stay in the student's history.

## Important notes

> [!NOTE]
> **A fine is applied to everyone you selected, or to no one.** If any selected student can't be fined, for example because they have not claimed their account yet, nothing is applied and the page tells you why.

> [!NOTE]
> **Selecting Apply fine twice does not fine twice.** If you really mean to fine the same students again for the same reason, review the fine again and apply it.

> [!NOTE]
> Manual payments always go to **checking**. If a student should end up with the money in savings, they can transfer it themselves.

> [!IMPORTANT]
> The credit applies only to students in the class you currently have selected. Checkboxes are not carried over when you switch classes.

## Troubleshooting

| What you see | What it means |
| --- | --- |
| "Please select at least one student to apply the payment." | No checkboxes were ticked. Select students in the left panel first. |
| "Manual credits must use a positive amount." | The amount was zero or negative. To take money away, use **Fine Students**. |
| "A balance changed since you reviewed this fine…" | A selected student's balance moved between your review and your confirmation, so nothing was applied. Check the updated review and select **Apply fine** again. |
| "…have not claimed their account and can't be fined." | One or more selected students have not set up their account. Nothing was applied. Clear those students and review again. |
| "This fine was already applied; it was not applied again." | You selected **Apply fine** more than once for the same review. The fine was applied once. |
| No recommended range is shown | Your class has no wage index yet. Set the payroll pay rate and expected weekly hours. |

## Related guides

- [Run Payroll](payroll-run.md)
- [Payroll Settings](payroll-settings.md)
- [Payroll History](payroll-history.md)
- [Bills](../bills/index.md)
