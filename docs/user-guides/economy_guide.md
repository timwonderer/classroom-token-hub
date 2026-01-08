---
title: Classroom Economy Guide
description: Teacher-friendly ranges and examples for pricing, rent, insurance, and balance checks.
roles: [teacher]
---

# Classroom Economy Guide

This guide helps teachers set prices and fees that keep the classroom economy balanced and motivating. Use it alongside the Economy Health page.

## Quick start
1. Set payroll first so you have a baseline for weekly earnings.
2. Note your Classroom Wage Index (CWI).
3. Use the ranges below to set rent, utilities, store pricing, fines, and insurance.
4. Do a quick affordability check before you announce changes.

## Key concept: Classroom Wage Index (CWI)

CWI is the expected weekly pay for a student who attends all sessions.

```
CWI = expected week_total_pay for perfect attendance
```

## Recommended ranges (based on CWI)

Use these ranges as starting points and adjust for your class goals. The ratios below apply to your chosen billing or pricing cycle.

### Rent

- Recommended range: 2.0x to 2.5x CWI per rent cycle
- Typical default: 2.25x CWI

Example: If CWI is 100, a rent cycle in the 200-250 range is a good starting point.

### Utilities or fixed fees

- Recommended range: 0.20x to 0.30x CWI per rent cycle
- Typical default: 0.25x CWI

### Store item pricing tiers

| Tier | Range |
| --- | --- |
| Basic | 0.02x to 0.05x CWI |
| Standard | 0.05x to 0.10x CWI |
| Premium | 0.10x to 0.25x CWI |
| Luxury | 0.25x to 0.50x CWI |

Example with CWI 100: basic items are 2-5, standard 5-10, premium 10-25, luxury 25-50.

### Insurance

- Premiums: 0.05x to 0.12x CWI (default 0.08x)
- Coverage: 3x to 5x premium (default 4x)
- Period payout cap: 6x to 10x premium (default 8x)

If you set coverage above 5x premium or a cap outside 6x-10x, expect more volatility.

### Fines

- Recommended range: 0.05x to 0.15x CWI (default 0.10x)

Try to keep fine sizes consistent so students can predict consequences.

### Inflation and events

Inflation should be applied across rent, utilities, store pricing, and insurance together so the economy stays balanced.

- Mild: 1% to 3%
- Moderate: 3% to 6%
- Severe: 6% to 10%

### Loans and APR

Risk bands:

- Low risk: 8% to 15%
- Medium risk: 15% to 35%
- High risk: 35% to 50%

Payment rule: keep installments under 40% of expected weekly earnings and avoid budgets that go negative for more than two cycles.

### Investments

- CDs: inflation rate + 1% to 3% (lock-in required)
- Bonds: inflation rate + 0% to 2% (low variance)
- Stocks: -30% to +30% swings (high risk)

### Savings interest

Savings interest is a motivation tool. Keep it modest.

- APY: 6% to 18%
- Monthly rate: 0.5% to 1.5% (default about 1%)

## Affordability check

A student with perfect attendance should still save around 10% of CWI after core costs.

```
weekly_savings = CWI - (rent / weeks_in_rent_cycle) - utilities - average_store_cost
weekly_savings >= 0.10 * CWI
```

If students are consistently broke, lower rent or fines, reduce utilities, or raise wages.

## For developers and tooling

For automated tooling and balancing rules, see the [Economy Specification](../technical-reference/ECONOMY_SPECIFICATION).
