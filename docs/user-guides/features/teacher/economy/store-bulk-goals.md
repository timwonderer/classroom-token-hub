---
title: Bulk Discounts and Collective Goals
category: features
subcategory: teacher-economy
roles: [teacher]
description: The two sale mechanics on the item form — bulk discounts and collective goals — how each one behaves, how to set them up, and how to sell a pack.
keywords: [bulk discount, pack, multipack, collective goal, whole class, target purchases, goal deadline, store item, sale mechanics]
related:
  - user-guides/features/teacher/economy/store-items
  - user-guides/features/teacher/economy/store-pricing
  - user-guides/features/teacher/economy/store-redemptions
  - user-guides/diagnostics/teacher/store
---

# Bulk Discounts and Collective Goals

## Overview

The item form offers two ways to sell something as more than a single fixed-price purchase. [Store Items](store-items.md) covers the fields; this page covers the behaviour behind them.

## What each one is for

| Mechanic | The idea | What happens when a student buys |
| --- | --- | --- |
| **Bulk discount** | Buying several at once lowers the price | The discounted figure on the buy screen is what is charged |
| **Collective goal** | The class buys toward a shared target | Progress counts, and the deadline closes the item to new purchases. **Reaching the target does nothing automatically** |

## Step-by-step instructions

### Bulk discounts

Tick **Enable Bulk Discount**, then set **Minimum Quantity for Discount** and **Discount Percentage (%)**. Both are required once enabled, the quantity must be greater than 1, and the percentage cannot exceed 100.

At the threshold, the student's buy screen recalculates: the hint reads *Bulk discount applied!*, **Total Price** drops, and a savings figure appears. That reduced figure is what their account is debited.

Two details worth knowing before you set a percentage:

- **The discount applies to the whole order, not to the units past the threshold.** "Buy 5+ for 20% off" at a price of 10 charges 40 for five, not 48. That is what the item card promises, so it is what is charged.
- **Below the threshold, nothing changes.** Four units at a threshold of five are charged in full.

The price is recalculated from your saved item settings at the moment of purchase, not from anything the student's browser sends, so a student cannot manufacture a discount by editing the page.

**Selling a pack.** There is no separate bundle setting: a pack is a bulk discount at the pack size. To sell three homework passes for 12, price the item at 5 and set **Buy 3+** at **20% off**. Three cost 12 together, and a student who only wants one can still buy one at 5. Each pass the student buys is a separate item: redeemed, decided, and expiring on its own, with no "uses left" counter.

> [!NOTE]
> Bulk discounts are available on **Delayed Use** and **Hall Pass** items only. Those types can hold several independent, unredeemed units. **Immediate Use** items are single-unit purchases, and a **Collective Goal** is a shared class pot rather than a student's multi-unit order.

### Collective goals

Set **Item Type** to **Collective Goal**, then choose a **Collective Goal Type**:

- **Fixed Number of Purchases** — you set **Target Number of Purchases**.
- **Whole Class Must Purchase (1 per person)** — the target follows your class size and updates as your roster changes.

**Goal Expiration Date** is required for this item type.

Both your card and the student's browse card show a *count/target* bar, counted as **distinct students who have purchased**, scoped to the class you are viewing — so a student buying twice moves the bar once, and one class's progress never bleeds into another's.

**The deadline closes the item.** Once the expiration date passes, a student attempting to buy is refused and told the goal has closed. This is the point of the date: past it the goal can no longer be reached, so taking more money for a share in it would be taking money for an outcome that cannot happen.

The item does not disappear from your catalogue, and its bar keeps showing the progress it reached. Nothing else changes on its own — in particular:

- **Reaching the target does nothing automatically.** The student's card changes to *Goal reached! Item will unlock soon.* No unlock follows, no one is notified, and no fulfillment is recorded. Students have already bought and paid in order to move the bar, so the "unlock" language describes your delivering the reward, not a step the app takes.
- **A goal that lapses unmet is deactivated and refunded automatically.** Within the hour after the deadline passes, the product is deactivated, every buy-in on a goal that fell short is closed out, the money is returned to the student who paid it, and the live progress bar clears. You do not have to do anything, and you should not also issue a manual credit — that would pay twice. A goal that *was* reached is left exactly as it is, because that reward is real and owed.

**Watch the bar and deliver the reward.** If the goal was reached, fulfilment is yours to carry out. If it was not, the app deactivates it, clears its live progress, and puts the money back.

## Deciding what to build

Three item shapes are available:

1. **A plain reward** — name, price, tier. This is what most items should be.
2. **A volume deal or pack** — a plain item with a bulk discount threshold, for anything a student sensibly buys more than one of.
3. **A collective goal you personally adjudicate** — set the target and the deadline, watch the bar, deliver the reward yourself if it is reached. An unmet goal deactivates, clears its live progress, and refunds itself; fulfilling a met one is yours to decide.

A **long-term goal item** — an expensive reward students save toward — is a pricing decision rather than a sale mechanic. See [Store Pricing Strategy](store-pricing.md) for how that interacts with the Classroom Wage Index.

## Important notes

> [!WARNING]
> **Meeting a collective goal is yours to act on.** The bar reaching its target does not unlock, notify, or fulfil anything. A goal that lapses *unmet* is deactivated, its live progress clears, and its buy-ins are refunded automatically; delivering a goal that was *reached* is your decision to carry out.

> [!NOTE]
> **Several bought at once are several items, not one item with uses left.** Each is redeemed, decided, and expires independently. If you are looking for a "3 of 5 remaining" counter, there isn't one, and the student's inventory showing three copies is the same information.

> [!NOTE]
> **Collective progress counts students, not purchases.** The bar moves once per student who has bought the item, within the class you are viewing. A student buying a second copy does not advance it, and each class period tracks its own progress against its own target.

> [!TIP]
> **Whole Class Must Purchase** is the more forgiving of the two goal types, because its target follows your roster. If a student joins or leaves mid-goal, the target moves with them instead of stranding the class one purchase short of a number you set weeks earlier.

## Related guides

- [Store Items](store-items.md)
- [Store Pricing Strategy](store-pricing.md)
- [Store Redemptions](store-redemptions.md)
- [Store and Redemptions Troubleshooting](../../../diagnostics/teacher/store.md)
