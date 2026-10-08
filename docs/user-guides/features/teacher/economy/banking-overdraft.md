---
title: Overdraft Rules
category: features
subcategory: teacher-economy
roles: [teacher]
description: Turn on savings-backed overdraft protection, set the flat overdraft fee, and understand what happens when a student cannot afford a purchase.
keywords: [overdraft, overdraft protection, overdraft fee, insufficient funds, savings, fine band, economic engine]
related:
  - user-guides/features/teacher/economy/banking-settings
  - user-guides/features/teacher/economy/banking-interest
  - user-guides/features/teacher/economy/economic-engine
---

# Overdraft Rules

## Overview

Overdraft settings decide what happens when a student tries to spend more than their checking account holds. The controls live in the **Overdraft** block on the **Settings** tab of **Economy > Banking**.

There are two of them, and they are independent — you can run either, both, or neither.

## Step-by-step instructions

### The two controls

| Control | What it does |
| --- | --- |
| **Overdraft protection** | *When on, a negative checking transaction pulls from savings before it overdraws.* |
| **Overdraft Fee (flat)** | The field's placeholder reads *Leave blank to disable*. It is never charged for a store purchase; see below. |

Finish with **Save Banking Settings**.

### What actually happens when a student comes up short

The system works through this in order:

1. **Checking covers it.** The purchase goes through. Nothing else happens.
2. **Checking is short, protection is on, and savings covers the whole shortfall.** The missing amount moves from savings to checking, then the purchase goes through. No fee.
3. **Checking is still short.** The purchase is refused. Nothing is charged, nothing is granted, and no fee is added, the way a declined card costs nothing at the register.

A purchase never takes checking below zero, whatever the fee is set to. Students see this before they buy: the store tells them how much they can spend, and it will not let them confirm a purchase they cannot afford.

### Partial savings does not help

Protection is all-or-nothing. If a student is $5 short and has $3 in savings, the transfer does not happen — $3 is not enough to close the gap, so the system moves nothing and the purchase is refused.

Students often read this as a bug. It is not. Tell them to move the money to checking themselves before buying.

### The Economic Engine range

Under the fee field, the page shows **Economic Engine range: X–Y** for your current mode, expressed as a percentage of CWI, along with suggested **Progressive tiers**. It is advice, not a limit — a fee outside the range still saves, and you get a red warning explaining why it is out of band.

If you have not set a pay rate yet, the line instead reads *Set a payroll pay rate and expected weekly hours to see the Economic Engine's recommended overdraft-fee range.*

## Important notes

> [!IMPORTANT]
> **Students cannot spend money they do not have.** Setting a fee does not unlock a purchase. A purchase that checking and a full savings transfer cannot cover is refused, with no fee.

> [!NOTE]
> **Where the fee applies.** The overdraft fee is for a bill payment that fails, not for spending in the store. No bill payment charges it today, so in practice setting it has no effect yet.

> [!NOTE]
> **Overdraft fees reuse the classroom fine band.** *A fee is only active while a value is set.* Clearing the field removes the fee entirely rather than setting it to zero.

> [!TIP]
> Protection on, fee blank, is the gentlest combination: savings quietly covers small gaps and nothing can go negative. It also teaches the lesson you probably want, which is that savings is there for a reason.

## Related guides

- [Banking Settings](banking-settings.md)
- [Interest and Payouts](banking-interest.md)
- [Economic Engine](economic-engine.md)
