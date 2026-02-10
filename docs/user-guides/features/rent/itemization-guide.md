---
title: Rent Itemization Guide
category: features
subcategory: rent
audience: teachers
---

# Rent Itemization Guide

**Audience:** Teachers
**Version:** 1.8.0+
**Route:** `/admin/settings/rent`

---

## Overview

Rent Itemization allows you to break down what students' rent payment covers, making the value transparent and giving students flexible alternatives if they can't afford full rent.

**Benefits:**
- **Transparency:** Students see exactly what they're paying for
- **Flexibility:** Students can buy individual items à la carte
- **Education:** Teaches value bundling and financial trade-offs
- **Incentive Structure:** Makes paying rent clearly advantageous

**Example:**
Instead of "$50 rent" being mysterious, students see:
- Desk: $20
- Chair: $15
- Locker: $10
- Supplies: $5
- **Total Value: $50** (vs. $65 if purchased separately)

---

## Getting Started

### Accessing Rent Itemization

1. Log in to your teacher account
2. Navigate to **Bills** section in sidebar
3. Click **Rent Settings**
4. Scroll to **Rent Itemization** section

---

## Setting Up Itemized Rent

### Step 1: Enable Rent

If not already enabled:

1. Check **Enable Rent** toggle at top of page
2. Set your **Base Rent Amount** (e.g., $50/month)
3. Configure rent frequency and due dates
4. Save settings

### Step 2: Add Rent Items

1. Scroll to **Rent Itemization** section
2. Click **Add Item** button
3. Fill in item details:

**Required Fields:**
- **Item Name:** What the item is (e.g., "Desk", "Locker", "Textbook")
- **Description:** Brief explanation of what this provides
- **Base Value:** Dollar amount this item represents in rent

**Item Type:**
Select one of the three item types:
1. **Privilege:** Ongoing benefits (Desk, Locker). Can be available in store.
2. **Per-Use:** Consumable goods or services (Pencil, Phone Call). Always in store.
3. **Hall Pass:** Adds to student's hall pass balance upon rent payment.

4. Click **Save Item**

### Step 3: Manage Your Items

**Reordering:**
- Drag items to rearrange display order
- Students see items in this order

**Editing:**
- Click **Edit** button on any item
- Update fields as needed
- Save changes

**Deleting:**
- Click **Delete** button
- Confirm deletion
- Note: This removes from store if was available there

---

## Understanding Base Value vs. Store Price

### Base Value

**What It Is:** The dollar amount this item contributes to rent

**Example:**
- If rent is $50 and you have 4 items
- Each item might have base value of $12.50
- Or vary by importance: Desk ($20), Chair ($15), Locker ($10), Supplies ($5)

**Purpose:**
- Shows students what they're getting for their rent
- Helps calculate total rent value

### Custom Store Price

**What It Is:** The à la carte price if student buys individually

**Pricing Strategy:**
- Usually **higher** than base value to incentivize paying rent
- Creates "bundle discount" for paying rent

**Example:**
- **Desk** base value: $20 in rent
- **Desk** store price: $25 individually
- Student saves $5 by paying rent vs. buying separately

**Recommended Markup:**
- 20-50% higher than base value
- Makes rent clearly the better deal
- But not so high students can't afford alternatives

---

## Item Types & Duration Options

### 1. Privilege Items

**What It Means:** Ongoing benefit valid for the rent period.

**Best For:**
- Desk/chair/locker access
- Textbook rental
- Classroom amenities

**Settings:**
- **Available in Store:** Toggle ON to offer as store alternative
- **Store Price:** À la carte price
- **Duration:** Valid until next rent due date

**Example:**
```
Item: Locker Access
Type: Privilege
Base Value: $10
Store Price: $15

Student buys locker access → Gets privilege badge → Lasts until next rent due date
```

### 2. Per-Use Items

**What It Means:** Consumable item or one-time service.

**Best For:**
- Consumables (paper, supplies, pencils)
- One-time services (print worksheet, phone call home)
- Late work passes

**Settings:**
- **Store Price:** Required (always available in store)
- **Free Uses Per Period:** (Optional) Rent payers get X free uses per rent cycle
- **Duration:** Per use (consumable)

**Example:**
```
Item: Extra Pencil
Type: Per-Use
Base Value: $1
Store Price: $2
Free Uses: 5

Rent payer gets 5 free pencils. Non-payer buys for $2 each.
```

### 3. Hall Pass Items

**What It Means:** Adds hall passes to student balance.

**Best For:**
- Bathroom passes
- Water fountain trips
- Locker visits

**Settings:**
- **Passes Granted:** Number of passes added when rent is paid
- **Duration:** Added to balance (no expiration)

**Example:**
```
Item: Bathroom Pass Bundle
Type: Hall Pass
Base Value: $5
Passes Granted: 3

Paying rent adds 3 passes to student's balance.
```

---

## Coverage Tracking

**How It Works:**
Rent payments now cover a specific date range (Coverage Period).
- **Start Date:** Last due date (or payment date)
- **End Date:** Next due date

**Privileges & Access:**
- Students are considered "Rent Active" only within their paid coverage period.
- Privileges expire automatically when the coverage period ends.
- Store alternatives for privileges are also valid only until the next rent due date.

---

## Store Integration

### How Auto-Sync Works

When you mark an item "Available in Store" (or use Per-Use type):

1. **Store Item Created Automatically:**
   - Name, description, price copied over
   - Set as "Rent Alternative" type
   - Configured with correct purchase limits
   - Inherits block visibility from rent settings

2. **Updates Propagate:**
   - Change rent item name → Store item name updates
   - Change store price → Store item price updates
   - Delete rent item → Store item removed

3. **Purchase Limits Set:**
   - Per Use items: No limit
   - Privilege items: Limit 1, expires automatically

### Student Store Experience

**What Students See:**

1. **On Rent Page:**
   - Itemized breakdown of what rent covers
   - Store prices for available alternatives
   - Total value comparison
   - Pro tip: "Pay rent to get everything for $50, or buy items individually for $65 total"

2. **In Store:**
   - Rent items appear as purchasable products
   - Clear labeling: "Included in rent" or "Rent alternative"
   - Duration info: "Per use" or "Valid until [date]"

3. **On Student Detail Page (Teachers See):**
   - Privilege badges showing what student has
   - Green badges: Covered by rent
   - Blue badges: Purchased individually

---

## Enhanced Purchase Restrictions

### How It Works

The "Prevent Purchase When Late on Rent" setting becomes dynamic:

#### Without Itemization (Original Behavior)
**Setting Enabled + Student Late on Rent:**
- Student blocked from ALL store purchases
- Message: "You must pay rent before making purchases"

#### With Itemization (New Behavior)
**Setting Enabled + Student Late on Rent:**
- Student CAN buy items covered by rent (at à la carte prices)
- Student BLOCKED from all other store items
- Message: "You can only purchase rent-covered items until you pay rent"

### The Incentive Structure

This creates powerful incentives:

**Scenario 1: Student Pays Rent**
- ✅ Gets all rent items included
- ✅ Can shop entire store
- ✅ Saves money (bundle discount)
- ✅ Full access to economy

**Scenario 2: Student Late on Rent**
- ⚠️ Must buy rent items at premium prices
- ❌ Blocked from other store items
- 💰 Pays more overall
- 🚫 Limited economy participation

**Educational Message:**
"Paying your bills on time gives you more options and saves you money."

---

## Example Setups

### Basic Setup: Classroom Essentials

```
Rent Amount: $40/month

Items:
1. Desk Access
   - Type: Privilege
   - Base: $15 | Store: $20

2. Chair Use
   - Type: Privilege
   - Base: $15 | Store: $20

3. Hall Pass Bundle
   - Type: Hall Pass
   - Base: $10 | Passes: 4

Total Base Value: $40
Total À La Carte: $55 (38% premium)
Savings by Paying Rent: $15
```

**Message to Students:**
"Pay $40 rent to get everything, or pay $55 to buy items separately."

### Advanced Setup: Mixed Duration Items

```
Rent Amount: $60/month

Items:
1. Desk & Chair
   - Type: Privilege
   - Base: $25 | Store: $35

2. Locker
   - Type: Privilege
   - Base: $20 | Store: $28

3. Textbook Rental
   - Type: Privilege
   - Base: $10 | Store: $15

4. Supply Pack (consumable)
   - Type: Per-Use
   - Base: $5 | Store: $2 | Free Uses: 3

Total Base Value: $60
Total À La Carte (excl. supplies): $78
Savings: $18 + supplies as needed
```

**Benefits:**
- Mix of long-term and per-use items
- Students understand different types of costs
- Teaches difference between fixed and variable expenses

---

## Best Practices

### Pricing Strategy

**DO:**
- Make total rent cheaper than buying separately (20-50% discount)
- Price store items 20-50% above base value
- Ensure most students can afford rent with normal earnings
- Make premium items optional, not required

**DON'T:**
- Price individual items too high (students need viable alternatives)
- Make rent so cheap there's no value in itemization
- Create too many items (4-6 is ideal)
- Make rent unaffordable for average student

### Item Selection

**Good Items:**
- Physical classroom resources (desk, locker, chair)
- Access privileges (textbook, technology, supplies)
- Consumables (paper, pencils, materials)
- Hall Pass bundles (adds value to rent)

**Avoid:**
- Public goods everyone needs (whiteboard access)
- Safety items (emergency supplies)
- Required educational materials
- Items that create inequality in learning

### Communication

**Tell Students:**
- What each item provides
- How store alternatives work
- Math showing rent is better deal
- When rent is due
- What happens if late

**Be Transparent:**
- Show the value breakdown
- Explain the intentional premium on à la carte items
- Discuss why paying rent gives options
- Connect to real-world rent/utilities concepts

---

## Troubleshooting

### "Students Not Understanding Value"

**Solutions:**
- Create visual comparison chart
- Do class activity comparing rent vs. individual costs
- Have students calculate savings
- Show privilege badges as visual reinforcement

### "Too Many Students Buying Individually"

**Possible Causes:**
- Store prices too close to base value
- Rent amount too high relative to earnings
- Students prefer flexibility

**Solutions:**
- Increase gap between base and store price
- Lower rent amount
- Add more items to rent bundle to increase value
- Check if earnings support rent payments

### "No One Using Store Alternatives"

**Possible Causes:**
- Everyone paying rent (good problem!)
- Store prices too high
- Items not appealing

**Solutions:**
- May not need store alternatives if rent working
- Lower store prices slightly
- Add luxury upgrades not in basic rent
- Survey students about interest

### "Sync Issues with Store"

**If store items not updating:**
1. Toggle "Available in Store" OFF then ON
2. Save rent settings
3. Check store management page
4. Report issue if persists

---

## Student Perspective

### What Students See on Rent Page

```
Your Monthly Rent: $50 due on the 1st

What Your Rent Covers:
✓ Desk Access ($20)
✓ Chair ($15)
✓ Hall Pass Bundle (4 passes)
✓ Supplies ($5)

Total Value: $50
```

### What Students See in Store

```
🏠 Rent Alternatives

These items are included in your rent. If you haven't paid rent,
you can buy them individually here.

[Desk Access] $25
📅 Valid until next rent payment (Feb 1)
✅ Included in rent | OR buy separately

[Extra Pencil] $2
📦 Per-Use Item
✅ 5 Free Uses remaining
```

### Privilege Badges (Teacher View)

When you view a student's detail page:

```
John's Rent Privileges:

🟢 Desk Access (Paid Rent)
🟢 Chair (Paid Rent)
🔵 Locker (Purchased - expires Feb 1)
```

- Green = Included in rent payment
- Blue = Purchased separately from store

---

## Related Documentation

- [Managing Rent Settings](managing-rent.md) - Complete rent configuration guide
- [Store Management](../store/creating-items.md) - Store item configuration
- [Economy Design Guide](../../economy_guide.md) - Balanced economy design
- [Student Guide - Rent](../../student_guide.md#rent) - Student perspective

---

## Feedback and Support

Have questions or suggestions about rent itemization?

- **In-App:** Help & Support → Report an Issue
- **Documentation:** [Teacher Manual](../../teacher_manual.md)
- **Community:** Share your rent setup strategies!

---

**Last Updated:** 2026-02-09
**Version:** 1.8.0
**Feature Status:** Production
