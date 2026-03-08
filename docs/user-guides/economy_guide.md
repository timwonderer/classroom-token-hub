---
title: Classroom Economy Guide
description: Teacher-friendly CWI guidance for policy modes, rent, store pricing, insurance, fines, and affordability.
roles: [teacher]
---

# Classroom Economy Guide

This guide explains how to use the Classroom Wage Index (CWI), economy policy mode, and the Economy Health page to keep classroom prices and expenses coherent.

## Quick start

1. Configure payroll so CWI can be calculated.
2. Open Economy Health and note the current CWI for the class you are reviewing.
3. Pick an economy policy mode: Tight, Default, or Comfortable.
4. Use the live tips in rent, store, and insurance settings to compare your values to the active policy.
5. Run a rebalance review if your current settings no longer match the policy you selected.

## Key concept: Classroom Wage Index (CWI)

CWI is the expected weekly pay for a student who attends all sessions.

```text
CWI = expected weekly pay for perfect attendance
```

The system uses weekly CWI as the baseline for rent, fixed fees, store pricing, insurance, fines, and affordability checks.

## Economy policy modes

Policy mode changes the recommendation bands the system uses. It does not rewrite old transactions.

### Tight

Use this when you want more budgeting pressure.

- Higher rent and fee pressure
- Lower savings target
- Tighter store and insurance guidance

### Default

Use this for the standard balanced economy.

- Moderate pressure
- Baseline savings target
- Balanced pricing bands across the economy

### Comfortable

Use this when you want more breathing room.

- Lower fixed pressure
- Higher savings target
- More forgiving store and insurance bands

## Recommended ranges by policy mode

All percentages below are weekly-CWI guidance.

### Rent

| Policy | Range | Typical midpoint |
| --- | --- | --- |
| Tight | 70%-80% | 75% |
| Default | 60%-75% | 67.5% |
| Comfortable | 50%-65% | 57.5% |

The app converts these weekly targets into monthly-equivalent recommendations when your rent is billed monthly.

### Utilities or recurring fixed fees

| Policy | Range | Typical midpoint |
| --- | --- | --- |
| Tight | 7%-12% | 9.5% |
| Default | 5%-10% | 7.5% |
| Comfortable | 4%-8% | 6% |

### Store pricing tiers

#### Tight

| Tier | Range |
| --- | --- |
| Basic | 1%-3% |
| Standard | 2%-4% |
| Premium | 4%-12% |
| Luxury | 12%-24% |

#### Default

| Tier | Range |
| --- | --- |
| Basic | 1%-3% |
| Standard | 2%-5% |
| Premium | 5%-15% |
| Luxury | 15%-30% |

#### Comfortable

| Tier | Range |
| --- | --- |
| Basic | 2%-4% |
| Standard | 3%-6% |
| Premium | 6%-18% |
| Luxury | 18%-35% |

### Insurance

#### Premium band

| Policy | Range | Typical midpoint |
| --- | --- | --- |
| Tight | 6%-14% | 9% |
| Default | 5%-12% | 8% |
| Comfortable | 4%-10% | 7% |

#### Maximum claim guidance

| Policy | Range vs premium |
| --- | --- |
| Tight | 2.5x-4.0x |
| Default | 3.0x-5.0x |
| Comfortable | 4.0x-6.0x |

#### Period cap guidance

| Policy | Range vs premium |
| --- | --- |
| Tight | 5.0x-8.0x |
| Default | 6.0x-10.0x |
| Comfortable | 8.0x-12.0x |

#### Waiting period guidance

| Policy | Recommended range |
| --- | --- |
| Tight | 10-14 days |
| Default | 7 days |
| Comfortable | 3-7 days |

### Fines

| Policy | Range | Typical midpoint |
| --- | --- | --- |
| Tight | 7%-18% | 11% |
| Default | 5%-15% | 10% |
| Comfortable | 4%-12% | 8% |

## Affordability check

A student with perfect attendance should still be able to save money after fixed costs and ordinary spending.

Minimum savings targets:

- Tight: about 5% of weekly CWI
- Default: about 10% of weekly CWI
- Comfortable: about 15% of weekly CWI

Conceptually, the system checks:

```text
weekly_savings = CWI - weekly_rent - weekly_insurance - average_store_cost
```

If students are consistently broke, lower rent, lower recurring fees, narrow fines, or review whether the selected policy mode matches the classroom pressure you actually want.

## Where the live tips appear

The shared CWI validation tool is available in:

- Rent settings
- Store item pricing
- Insurance policy creation and editing
- Payroll fine configuration

Insurance guidance is the most detailed. It checks:

- premium
- maximum claim amount
- maximum payout per period
- waiting period days

## Rebalancing

Changing policy mode updates the target profile immediately, but your class settings stay where they are until you change them.

Use the rebalance review when you want the system to propose updated values for supported settings.

## For developers and tooling

For authoritative economy rules, see:

- [DOM-ECON-001_Economy_Balance_Checker.md](../DOMAINS/ECONOMY_DESIGN/DOM-ECON-001_Economy_Balance_Checker.md)
- [DOM-ECON-002_Economy_Specification.md](../DOMAINS/ECONOMY_DESIGN/DOM-ECON-002_Economy_Specification.md)
- [FEAT-ECON-001_Policy_Mode_and_Rebalancer.md](../FEATURES/ECONOMY/FEAT-ECON-001_Policy_Mode_and_Rebalancer.md)
