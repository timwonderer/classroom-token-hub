---
title: Store Items
category: features
subcategory: teacher-economy
roles: [teacher]
description: Create, price, and retire store items — including bundles, bulk discounts, collective goals, and the difference between deactivating and deleting.
keywords: [store, items, pricing, tier, inventory, bundle, bulk discount, collective goal, deactivate, delete, rent perk, CWI]
related:
  - user-guides/features/teacher/economy/store-bundles-goals
  - user-guides/features/teacher/economy/store-pricing
  - user-guides/features/teacher/economy/store-redemptions
  - user-guides/features/teacher/economy/economic-engine
  - user-guides/diagnostics/teacher/store
---

# Store Items

## Overview

**Economy > Store** opens **Store Management**, a five-tab page. Two of those tabs belong to items: **Manage Items** is your catalogue, and **Add New Item** is the form that fills it.

An item is worth building carefully. Price is only one of its dials — item type decides whether a student gets the thing instantly or waits for you, and the bundle, discount, and collective-goal settings change what a single purchase even means.

## Step-by-step instructions

### Creating an item

Open the **Add New Item** tab. The form is five sections.

#### Basic Information

| Field | What it does |
| --- | --- |
| **Item Name** | What students see in the store. Required. |
| **Price** | Required. Checked live against your Classroom Wage Index — see *Pricing against the CWI* below. |
| **Pricing Tier (optional)** | Organisational grouping. Selecting one shows a recommended price range. |
| **Description** | Free text, shown on the item. |
| **Item Type** | Required. Decides the whole redemption path — see the table below. |
| **Item is Active** | Off means students never see it. |
| **Bypass CWI Warnings** | *Suppress live CWI warnings for this item and hide it from Economy Health.* |
| **Long-Term Goal Item** | *For expensive items students save for over many weeks (won't trigger CWI warnings).* |
| **Visible to Periods/Blocks** | Hold Ctrl/Cmd to select several. Leave empty to show to all periods. |

**Item Type** is the decision that matters most:

| Type | What happens when a student buys |
| --- | --- |
| **Immediate Use** | The student gets it at once. It never enters your approval queue. |
| **Delayed Use** | The purchase lands in **Pending Redemption Requests** and waits for you to approve or refund. |
| **Collective Goal** | Nothing unlocks until the class hits the target you set. |
| **Hall Pass** | Adds to the student's hall-pass balance rather than granting an object. |

The four **Pricing Tier** options are **Basic**, **Standard**, **Premium**, and **Luxury**. Selecting one shows a **Recommended range** in dollars, computed from your Classroom Wage Index. Note that the percentages printed in the dropdown labels do not match the range the app actually recommends — see [Store Pricing Strategy](store-pricing.md) for the real bands and how to read them.

#### Inventory & Limits

- **Inventory** — total redemptions available across everyone. Leave blank for unlimited.
- **Purchase Limit per Student** — caps one student's repeat buys. Leave blank for no limit.

#### Bundle Settings

Tick **This is a Bundled Item** and set **Bundle Quantity**. The form describes this as *Bundled items give students multiple uses that can be redeemed separately*; the quantity is required and must be greater than 1 once the box is ticked.

One purchase is charged once and delivers that many separately redeemable items. Available on **Delayed Use** and **Hall Pass** items only — those are the two types that can sit unredeemed in an inventory. See [Bundles, Bulk Discounts, and Collective Goals](store-bundles-goals.md).

#### Bulk Discount Settings

Tick **Enable Bulk Discount**, then set **Minimum Quantity for Discount** and **Discount Percentage (%)**. Both are required once enabled; the percentage cannot exceed 100.

This is distinct from a bundle: a bundle changes what one purchase contains, a bulk discount changes the price when a student buys several. At or above the threshold the discount applies to the whole order, not only to the units past it. See [Bundles, Bulk Discounts, and Collective Goals](store-bundles-goals.md).

Bulk discounts are available on **Delayed Use** and **Hall Pass** items only. Those types can hold several independent, unredeemed units. **Immediate Use** items are single-unit purchases, and a **Collective Goal** is a shared class pot rather than a student's multi-unit order.

#### Collective Goal Settings

> [!NOTE]
> This setting only applies to Collective Goal items.

- **Fixed Number of Purchases** — you set **Target Number of Purchases**.
- **Whole Class Must Purchase (1 per person)** — *Every student in the class must purchase. The target dynamically updates based on class size.*

**Goal Expiration Date** is required for this item type. If the goal is not reached, the hourly expiry sweep deactivates the product, refunds every buyer their initial payment, and clears the live progress bar. The expired product remains in history but cannot be reactivated as the same goal; create a new goal if you want to try again.

#### Advanced Settings

- **Auto-Delist Date** — the item is automatically hidden on this date.
- **Item Expiry in Days** — for delayed-use items, how long the student has before their purchase expires.
- **Redemption Prompt** — optional text shown to students when they redeem a delayed-use item, so you collect what you need up front. Example: *Please describe when and where you'd like to use this item.*

Finish with **Save Item**.

### Reading the catalogue

**Manage Items** shows one card per item. Each card carries:

- Name, price, and item type
- **Active** or **Inactive**
- Tier badge, a *n bundle* badge, and a *n% off n+* badge where those apply
- **Inventory** and **Limit per student** (**Unlimited** / **None** when unset)
- **Active In** — the class badges, or **All Classes**
- For collective items: a per-class progress bar reading *count/target*, plus **Deadline** if one is set

Before you have created anything: *No store items yet. Use the Add New Item tab to get started.*

### Editing, deactivating, and deleting

Each card has three controls in its footer: **Edit**, **Deactivate**, and **Delete Permanently**.

**Deactivate** asks for confirmation and then *removes it from the student store but preserves purchase history. You can reactivate it later.*

**Delete Permanently** is a different operation. It warns *This action cannot be undone* and *completely removes the item from the database and deletes related purchase records.* Ledger transaction history survives — the money movement stays on record — but the purchase records tying students to that item do not.

### Rent-linked items

An item carrying a **Rent Perk** badge is one you built here with the rent-link toggle on. It is an ordinary store item in every other respect — edit, deactivate, and delete all work normally, and this page is the only place it is defined.

What the toggle changes is what paying rent does: students who pay receive the item as a perk. That set is read at the start of each cycle, so adding or removing a rent-linked item takes effect on the **next** cycle and never disturbs one already open.

A student holding rent perks sees them in their **My Items** tab as free uses. Those uses are not a discount in the store — if the same student buys the item again, they pay the listed price.

## Pricing against the CWI

The price field validates live against your Classroom Wage Index as you type, and tier selection shows a **Recommended range** to price into.

Two checkboxes opt an item out of that scrutiny, and they are not the same thing:

- **Long-Term Goal Item** — the honest option for a genuinely expensive reward students save toward for weeks. It excludes the item from CWI balance checks.
- **Bypass CWI Warnings** — a blunter override. It silences warnings *and* hides the item from Economy Health, so the item stops contributing to your economy's health picture entirely.

## Important notes

> [!WARNING]
> **Deactivate and Delete are not two strengths of the same action.** Deactivating hides an item and keeps its history. Deleting destroys the purchase records that connect students to it. If you only want the item gone from the store, deactivate.

> [!IMPORTANT]
> **Rent-linked items are ordinary store items carrying a toggle.** They are built here, not in Rent Settings. You build one like any other item and tick the rent-link option; a change to the rent-linked set takes effect on the *next* rent cycle, so adding or removing one never disturbs a cycle already open.

> [!WARNING]
> **Meeting a collective goal is not automatic.** The deadline is enforced — the item stops selling once it passes — but reaching the target unlocks nothing on its own. A goal that lapses *unmet* refunds itself; a goal that was *reached* is yours to fulfil. Read [Bundles, Bulk Discounts, and Collective Goals](store-bundles-goals.md) before you build one.

> [!TIP]
> Use **Delayed Use** with a **Redemption Prompt** for anything that costs you classroom time — seating changes, homework passes, music choice. The prompt collects the details when the student asks, instead of leaving you to chase them.

## Related guides

- [Bundles, Bulk Discounts, and Collective Goals](store-bundles-goals.md)
- [Store Pricing Strategy](store-pricing.md)
- [Store Redemptions](store-redemptions.md)
- [Economic Engine](economic-engine.md)
- [Store and Redemptions Troubleshooting](../../../diagnostics/teacher/store.md)
