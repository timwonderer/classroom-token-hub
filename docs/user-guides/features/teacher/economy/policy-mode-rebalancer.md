---
title: Economic Policy and Rebalancing
category: features
subcategory: teacher-economy
roles: [teacher]
description: Choose an economic policy mode, review the rent rebalance, and schedule or apply the change.
keywords: [economic policy, rebalance, policy mode, tight, comfortable, cwi, economy health, effective date, scheduled]
related:
  - user-guides/features/teacher/economy/economic-engine
  - user-guides/features/teacher/economy/payroll-settings
  - user-guides/economy_guide
---

# Economic Policy and Rebalancing

## Overview

The **Economic Policy** card sits on the Economic Engine page, below the CWI card. It does one thing: it sets how much of a student's weekly earnings your fixed costs are allowed to consume.

Every pricing recommendation on the page — rent range, insurance premium range, fine range, store tiers, minimum weekly savings — is derived from your CWI *and* the active policy. Changing the policy changes all of them at once. It does not change any price by itself.

The **Rent Rebalance Preview** is the second half: it compares your live rent setting against the new policy and offers to update it for you. Other pricing domains remain on their own settings pages.

## Step-by-step instructions

### Choosing a policy mode

1. In the teacher sidebar, open **Economy** and select **Economic Engine**.
2. Scroll to the **Economic Policy** card. Three modes are shown side by side:

   | Mode | Summary | What it means |
   | --- | --- | --- |
   | Tight | More budgeting pressure | A leaner economy with less surplus and more deliberate spending |
   | Default | Balanced economy | The standard baseline with moderate pressure and stable survival margins |
   | Comfortable | More breathing room | A more forgiving economy with lower fixed pressure and larger student margin |

   The mode currently in force is selected and its tile is outlined.
3. Select the mode you want and choose **Save Policy Mode**.

The card header carries a badge — **Pricing Aligned**, **Pricing slightly off**, or **Pricing Significantly Off** — telling you how well your current settings match the active policy. Below the mode tiles, one small card per category (rent, insurance, store, and so on) repeats that judgement with a count of checker notes.

After you save, the page reopens with the rebalance review already showing.

### Reviewing the recommended rebalance

You can also reach this at any time with **Review Recommended Rebalance**, next to the save button. The button only appears once payroll is configured.

The **Rent Rebalance Preview** table has four columns:

| Column | What it shows |
| --- | --- |
| Apply | A checkbox. Changes the engine is confident about are pre-checked |
| Feature | The setting that would change |
| Current | What it is set to now |
| Recommended | What the active policy suggests |

Uncheck anything you want to keep as-is. If your settings already match the policy closely enough, no table appears — you get a green message saying no changes are recommended.

In practice the table holds one row at most. **Rent is the only setting the rebalance can change.** Insurance premiums, fines, and store prices all have recommended ranges on this page, but none of them appear here and none of them are rebalanced — you adjust those on their own settings pages.

### When it takes effect

You don't pick a date. Each change takes effect the one way it can:

- **Rent and the rent late penalty** are saved now and start with the first rent bill that has not been sent yet. Bills students already have keep their amounts.
- **Store prices and the overdraft fee** have no cycle to wait for, so they change as soon as you apply.

Select **Apply Selected Rebalance** to commit, or **Cancel** to leave everything alone.

## Important notes

> [!IMPORTANT]
> **Nothing is retroactive.** A policy change updates the recommendation profile and, if you rebalance, your forward-looking settings. It never rewrites past payroll, rent charges, or ledger entries.

> [!NOTE]
> **A scheduled rebalance is already saved.** A rent change is saved right away with the date it starts, and the Economic Engine shows an **Economy Update Scheduled** badge with that date. Nothing else has to happen for it to start: the next rent bill is simply sent with the new amount.

> [!NOTE]
> **Changing the policy mode does not undo a scheduled rebalance.** The new rent is already saved in your rent settings. To change it before it starts, save the amount you want on the **Rent** settings page.

> [!TIP]
> Not sure which mode to pick? Stay on **Default**, watch the Economic Balance alerts and the savings figure for a week or two, then move tighter or more comfortable based on what you actually see students able to afford.

> [!NOTE]
> Everything except rent is edited on its own settings page. The recommended ranges on the Economic Engine tell you what to aim for; the rebalance does not carry them over for you.

## Related guides

- [Economic Engine](economic-engine.md)
- [Payroll Settings](payroll-settings.md)
- [Classroom Economy Guide](../../../economy_guide.md)
