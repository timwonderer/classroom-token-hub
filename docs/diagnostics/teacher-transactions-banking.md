---
title: Teacher Transactions and Banking
category: diagnostics
roles: [teacher]
related:
  - diagnostics/teacher-attendance-payroll
  - diagnostics/teacher-store
---

# Transactions and Banking

## If balances look wrong, check these first
- Confirm the student is on the correct join code/class period.
- Check for voided transactions in the ledger.
- Use the Backfill Join Codes tool if legacy data is out of sync.

## If students cannot transfer funds
- Banking is enabled for that class period.
- Students must enter their passphrase to transfer.
- Transfers require enough funds in the source account.

## This is expected when...
- Overdraft protection moves savings to checking if enabled.
- Overdraft fees post when checking goes negative and fees are enabled.
- Interest posts monthly based on the banking settings.

## This cannot happen unless...
- A voided transaction still affects the balance (voids remove it from totals).

## Quick evidence to collect
- The transaction ID, type, and join code.
- The student's class period and the time window in question.
