---
title: Transactions
category: features
subcategory: teacher-economy
roles: [teacher]
description: Review the class transaction history and void incorrect entries from the Banking page.
keywords: [transactions, history, void, banking, ledger]
related:
  - user-guides/features/teacher/economy/banking-settings
  - user-guides/diagnostics/teacher/transactions-banking
---

# Transactions

## Overview

Transactions are the complete record of money movement in your class: payroll deposits, store purchases, rent charges, transfers, fees, and interest payouts. They live on the **Banking** page, under the **Transactions** tab.

## Step-by-step instructions

### Opening the transaction history

1. In the teacher sidebar, open **Economy**.
2. Select **Banking**.
3. Select the **Transactions** tab.

The **Overview** tab also shows a short recent-activity list with a **View All Transactions** button that takes you to the same tab.

### Filtering

The filter row above the table lets you narrow the history:

| Filter | What it does |
| --- | --- |
| Account | Limits to checking or savings |
| Type | Limits to one kind of entry, such as a purchase or a transfer |
| From / To | Limits to a date range |
| Student | Matches on student name |

Select **Apply Filters** to run the filter, or **Clear Filters** to return to the full history. The count beside the buttons shows how many entries you are looking at out of the total.

Each row shows the date, student, type, account, amount, and description. Student names link to that student's detail page.

### Voiding a transaction

If an entry is wrong, you can void it.

1. Find the row in the Transactions tab.
2. Select the **cancel** icon in the Actions column.
3. Confirm when prompted.

The row stays in the table, marked **VOID** and greyed out, and its amount no longer counts toward the student's balance.

## Important notes

> [!WARNING]
> **Voiding cannot be undone.** There is no un-void action. If you void the wrong entry, you will need to reissue the amount — for example through a manual payment.

> [!NOTE]
> Voided transactions stay visible on purpose. The ledger is an audit trail, so entries are never deleted, only neutralized.

## Why it works this way

**What you might expect:** you can delete a wrong entry, or set a student's balance to the right number.

**What Classroom Token Hub does instead:** a balance is the sum of the entries in this table and nothing else. You can void an entry, but it stays visible, marked **VOID**. You cannot delete an entry or type in a balance.

**Why:** the app never allows silent balance edits or unlogged interventions. Every correction is a visible transaction that students can read back, because students can only trust an economy whose changes they can check. The rules bind you as well as them.

### If this doesn't fit your class

- [ClassBank](https://www.classbank.com/) lets teachers [delete transactions](https://help.classbank.com/en/articles/6583467-delete-transactions), one at a time or in bulk, and [reset student balances](https://help.classbank.com/en/articles/8135776-reset-student-balances) to zero.

*Checked against each product's own website on 29 October 2026. Classroom Token Hub is not affiliated with any of them. Check their current features and pricing yourself. [More on this](../design-choices.md).*

## Related guides

- [Banking Settings](banking-settings.md)
- [Interest and Payouts](banking-interest.md)
- [Transactions and Banking Troubleshooting](../../../diagnostics/teacher/transactions-banking.md)
