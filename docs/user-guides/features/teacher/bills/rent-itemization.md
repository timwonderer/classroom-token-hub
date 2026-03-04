---
title: Rent Itemization
category: features
subcategory: teacher-bills
roles: [teacher]
description: Break rent into itemized charges and configure store alternatives.
keywords: [rent, itemization, utilities, itemized rent]
related:
  - user-guides/features/teacher/bills/rent-settings
  - user-guides/features/teacher/bills/rent-behaviors
  - user-guides/diagnostics/teacher-rent-itemization
---

# Rent Itemization

## Overview
Itemization allows you to break flat rent into smaller, understandable line-item charges (like "Desk Rent", "Tablet Fee", or "Locker"). Each item can be purchased individually from the store at a premium price, creating a real-world economics lesson about bundle discounts.

## When to Use Itemization

Use itemization when you want to:
- **Show rent breakdown** - Students see what each piece of rent costs (transparency)
- **Enable store alternatives** - Students can buy individual items à la carte instead of paying full rent
- **Create purchase restrictions** - Late rent payers can only buy rent-covered items
- **Teach economics** - Compare bundled (rent) vs. individual (store) pricing

## Step-by-Step Instructions

### Setting Up Itemized Rent

1. Navigate to **Bills > Rent** in the teacher sidebar and open the **Itemization** tab.

2. Add your first rent item:
   - **Item Name**: Clear description (e.g., "Desk", "Locker", "Wifi Access")
   - **Base Value**: What this item represents (e.g., $5 of a $30 rent)
     - ⚠️ Note: Base values don't need to sum exactly to rent total
     - They show relative worth to students
   - **Duration**: Choose one:
     - **Per Rent Period** - Students buy once per billing cycle (1 limit per period)
     - **Per Use** - Students buy each time (like consumables or daily passes)
   - **Available in Store**: Toggle ON to allow individual purchases

3. Set the store price (if available in store):
   - Price is typically 20-50% higher than base value
   - Creates incentive: "Pay $30 rent vs. $40+ individually"
   - Example: Desk base $5 → Store price $8

4. Repeat for all rent components (desks, lockers, supplies, hall passes, etc.)

5. Save your changes and review:
   - Total rent should equal sum of base values (or close)
   - Store shows your items at the premium prices
   - Privilege badges appear when students purchase

### Understanding Privilege Badges

Students see colored badges on their profile after purchasing:
- 🟢 **Green** - Included in paid rent (automatic)
- 🔵 **Blue** - Purchased individually from store
- **No badge** - Not owned or expired

### How Store Integration Works

When a rent item is available in store:
- **Store Sync**: Automatically creates store items named "Desk (Rent Alternative)", "Locker (Rent Alternative)", etc.
- **No Double-Charging**: If a student buys from store, rent charges are adjusted
- **Price Link**: Store price should be higher than base value (same discipline)
- **Example Workflow**:
  1. Student pays $30 rent → Gets all rent items as green badges
  2. OR pays nothing + buys individual items: $8 desk + $5 locker + $10 supplies = $23
  3. Later buys more from store without double-charging for rent items

## Important Notes

> [!IMPORTANT]
> **Base Value vs. Store Price:** These are different!
> - Base Value = Portion of rent (e.g., $5)
> - Store Price = À la carte purchase (e.g., $8)
> - Store price is usually 20-50% higher to incentivize paying rent

> [!NOTE]
> **Purchase Restrictions:** If you enable "Prevent Purchase When Late", students who owe rent can only buy rent-covered items. Non-rent store items are blocked. This encourages paying rent before buying luxuries.

> [!TIP]
> **Student Confusion Prevention:**
> - Explain in class: "Rent bundles items cheaper than buying separately"
> - Create a comparison chart: Rent $30 vs. Individual items $40+
> - Use real-world parallel: Apartment rent includes utilities, internet, etc.

## Common Setup Mistakes

❌ **Making base values sum exactly to rent** - Not required; they show relative worth
❌ **Setting store price lower than base value** - Defeats the purpose of incentive
❌ **Not explaining to students** - They'll be confused by per-use vs per-period
❌ **Mixing per-use and per-period** - Causes expectation confusion

## Related guides
- [Rent Settings](rent-settings.md)
- [Rent Behaviors](rent-behaviors.md)
- [Teacher Rent Itemization Diagnostics](../../../diagnostics/teacher/rent-itemization.md) - Troubleshooting guide
