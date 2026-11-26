---
title: Classroom Economy Guide
category: user-guides
description: The recommended ranges for rent, store prices, insurance, fines, collective goals and savings interest, how policy modes change them, and how to check your economy adds up.
roles: [teacher]
related:
  - user-guides/features/teacher/economy/economic-engine
  - user-guides/features/teacher/economy/policy-mode-rebalancer
  - user-guides/features/teacher/economy/store-items
  - user-guides/features/teacher/bills/insurance-policies
  - user-guides/features/teacher/economy/banking-interest
---

# Classroom Economy Guide

This guide collects the ranges CTH recommends for the prices and charges you set, so your class economy stays balanced: students can pay their bills, still save, and still have a reason to work.

Every range here is **advice, not a rule**. CTH shows these ranges where you set each price, and warns you when you go outside one, but your number always stands. Nothing is ever changed for you.

## Quick start

1. **Set payroll first.** Every range is a share of your class's weekly pay, so the pay rate has to exist.
2. **Set expected weekly hours** on the Economic Engine. Together with the pay rate, that defines your **CWI** (below).
3. **Pick a policy mode**: Tight, Default or Comfortable. If you are unsure, stay on Default.
4. **Set prices** using the ranges below. The setting pages show the same ranges for your class in dollars.
5. **Run the affordability check** at the end of this guide before you announce changes to students.

## Classroom Wage Index (CWI)

CWI is what a student earns in a typical full week:

```text
CWI = pay rate × expected weekly hours
```

Everything else is measured against it, so the same advice works for a class paid $5 a week and a class paid $500. Until both inputs are set, the Economic Engine shows **Needs setup** and no ranges appear.

> [!NOTE]
> **All ranges are per week.** For something charged monthly, CTH compares it against about 4.3 weeks (30 days ÷ 7). Divide a monthly amount by 4.3 before comparing it with a weekly range below.

## Policy modes

The policy mode sets how tight the economy feels. It changes the **recommended** prices, the savings target and the interest ceiling. It never changes what you have already set. To move your current settings toward the new mode, use the rebalance review ([Economic Policy and Rebalancing](features/teacher/economy/policy-mode-rebalancer.md)).

| Mode | Feels like |
| --- | --- |
| **Tight** | Less surplus; students budget carefully and save less |
| **Default** | A balanced starting point |
| **Comfortable** | More breathing room and a larger cushion |

## Recommended ranges

All as a share of CWI, per week:

| What | Tight | Default | Comfortable |
| --- | ---: | ---: | ---: |
| Savings target (what a student should be able to keep) | 5% | 10% | 15% |
| Rent | 30% to 40% | 35% to 50% | 40% to 55% |
| Insurance premium | 6% to 14% | 5% to 12% | 4% to 10% |
| Fine, per incident | 5% to 10% | 5% to 12% | 7% to 15% |
| Collective goal amount | 1× to 3× | 1× to 5× | 1.5× to 7× |

**Rent** is the biggest fixed cost, so set it first. The rent settings page shows your class's range in dollars.

**Fines** use the fine range, which the **Fine Students** review shows ([Manual Payments](features/teacher/economy/manual-payments.md)). Rent late fees use the same range. Keep fines consistent so students can predict consequences.

**Collective goals** are store items the class buys toward together ([Bulk Discounts and Collective Goals](features/teacher/economy/store-bulk-goals.md)). The range applies to the item's **Goal Amount**, and the item form shows it for your class in dollars.

### Store prices by economic role

Every store item has an **economic role**. The role describes what the purchase means; it does not set the price. The ranges are the same in every policy mode:

| Economic role | Price range | Meant for |
| --- | ---: | --- |
| **Necessity** | 1% to 10% of CWI | Routine or important purchases |
| **Convenience** | 11% to 20% of CWI | Optional purchases that add flexibility |
| **Add-on** | 21% to 30% of CWI | Treats and rewards students may need to save for |

A price outside its role's range is allowed; the store page tells you where it falls. Choosing **Necessity** is a description only: whether an item stays available while a student's rent is overdue is its own setting ([Store Items](features/teacher/economy/store-items.md)).

### Insurance: price versus coverage

Insurance has two separate settings, and only one of them follows the policy mode:

- **The premium (price)** follows the mode, using the range in the table above. The insurance page suggests a premium for your class.
- **The coverage** (how much is reimbursed, how many claims, how long the filing window is, any waiting period) comes from the plan you build and its tier. Changing the policy mode **never** changes coverage.

Coverage options for each insurance type are in [Insurance Policies](features/teacher/bills/insurance-policies.md).

### Savings interest

Interest should make saving worthwhile without letting money grow on its own faster than students can earn it. So each mode sets a limit on how fast savings may **double**:

| Mode | Savings may not double faster than | Roughly the highest APY |
| --- | ---: | ---: |
| Tight | 6 years | about 12% |
| Default | 4 years | about 19% |
| Comfortable | 2 years | about 41% |

These are ceilings, not suggestions; most classes do well well below them. The banking page shows your class's ceiling and warns you if you set a rate above it. Simple and compound interest are explained in [Savings Interest](features/teacher/economy/banking-interest.md).

## Affordability check

Before announcing new prices, check that a student who works a full week can pay their fixed costs and still meet the savings target:

```text
left over = CWI − weekly rent − weekly insurance premium − a typical week of store spending
```

`left over` should be at least the savings target for your mode (5%, 10% or 15% of CWI). If it is not, lower rent or the premium, raise pay, or move to a more comfortable mode.

The Economic Engine's **Economic Balance** alerts run a version of this check for you.

## Related guides

- [Economic Engine](features/teacher/economy/economic-engine.md)
- [Economic Policy and Rebalancing](features/teacher/economy/policy-mode-rebalancer.md)
- [Store Items](features/teacher/economy/store-items.md)
- [Insurance Policies](features/teacher/bills/insurance-policies.md)
- [Savings Interest](features/teacher/economy/banking-interest.md)
