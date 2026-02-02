---
title: Rent Itemization Guide
category: features
subcategory: rent
audience: teachers
---

# Rent Itemization Guide

**Audience:** Teachers
**Version:** 1.7.0+
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

**Store Integration (Optional):**
- **Available in Store:** Toggle ON to offer as store alternative
- **Custom Store Price:** Set à la carte price (usually higher than base value)

**Purchase Duration:**
- **Per Use:** Student buys each time (unlimited purchases)
- **Per Rent Period:** Buy once, lasts until next rent due

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

## Purchase Duration Options

### Per Use Items

**What It Means:** Student must buy every time they want to use it

**Best For:**
- Consumables (paper, supplies, pencils)
- One-time privileges (extra bathroom pass, laptop charger)
- Items that naturally expire with use

**Settings:**
- Unlimited purchases allowed
- No expiration date
- Student can buy multiple times

**Example:**
```
Item: Extra Supplies Pack
Base Value: $5
Store Price: $7
Duration: Per Use

Student buys supplies pack → Uses it → Can buy again next time
```

### Per Rent Period Items

**What It Means:** Student buys once, can use until next rent is due

**Best For:**
- Desk/chair/locker access
- Textbook rental
- Long-term privileges
- Classroom amenities

**Settings:**
- Limit 1 purchase per student
- Expires when next rent payment due
- Acts like mini-rent for that item

**Example:**
```
Item: Locker Access
Base Value: $10
Store Price: $15
Duration: Per Rent Period

Student buys locker access → Gets privilege badge → Lasts until next rent cycle
```

**Expiration Logic:**
- If rent is due monthly on the 1st
- Student buys locker access on January 5th
- Access expires February 1st (next rent due date)
- Student must buy again or pay full rent

---

## Store Integration

### How Auto-Sync Works

When you mark an item "Available in Store":

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
   - Per Rent Period items: Limit 1, expires automatically

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
   - Base: $15 | Store: $20 | Per Rent Period

2. Chair Use
   - Base: $15 | Store: $20 | Per Rent Period

3. Supply Cabinet Access
   - Base: $10 | Store: $15 | Per Month

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
   - Base: $25 | Store: $35 | Per Rent Period

2. Locker
   - Base: $20 | Store: $28 | Per Rent Period

3. Textbook Rental
   - Base: $10 | Store: $15 | Per Rent Period

4. Supply Pack (consumable)
   - Base: $5 | Store: $7 | Per Use

Total Base Value: $60
Total À La Carte (excl. supplies): $78
Savings: $18 + supplies as needed
```

**Benefits:**
- Mix of long-term and per-use items
- Students understand different types of costs
- Teaches difference between fixed and variable expenses

### Premium Setup: Luxury Classroom

```
Rent Amount: $100/month

Items:
1. Premium Desk (standing desk)
   - Base: $30 | Store: $45 | Per Rent Period

2. Ergonomic Chair
   - Base: $25 | Store: $38 | Per Rent Period

3. Locker XL
   - Base: $20 | Store: $30 | Per Rent Period

4. Technology Package (iPad access)
   - Base: $15 | Store: $25 | Per Rent Period

5. Unlimited Supplies
   - Base: $10 | Store: N/A | Per Rent Period

Total Base Value: $100
Total À La Carte: $138
Savings: $38
```

**Educational Goals:**
- Teaches value of premium options
- Demonstrates quality vs. cost tradeoffs
- Students see luxury has price but also value

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
- Optional upgrades (premium desk, extra storage)

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
✓ Locker ($10)
✓ Supplies ($5)

Total Value: $50

💡 Pro Tip:
If you pay rent, you get everything included!
If you buy items separately from the store:
- Desk: $25 (+ $5)
- Chair: $20 (+ $5)
- Locker: $15 (+ $5)
- Supplies: $7 (+ $2)
Total à la carte: $67 (+ $17 more!)

Pay rent to save $17!
```

### What Students See in Store

```
🏠 Rent Alternatives

These items are included in your rent. If you haven't paid rent,
you can buy them individually here.

[Desk Access] $25
📅 Valid until next rent payment (Feb 1)
✅ Included in rent | OR buy separately

[Chair] $20
📅 Valid until next rent payment (Feb 1)
✅ Included in rent | OR buy separately
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

## Advanced Configurations

### Progressive Rent

Create different "rent tiers" using store items:

**Basic Rent: $40**
- Standard desk
- Standard chair
- Basic locker

**Premium Upgrades (Store):**
- Standing desk upgrade: +$15
- Ergonomic chair upgrade: +$10
- Locker XL upgrade: +$8

Students pay base rent, can upgrade components individually.

### Seasonal Items

Add/remove items based on time of year:

**Fall:** Include textbook rental
**Winter:** Add coat hook access
**Spring:** Include outdoor seating option

### Experiment With Models

Test different setups and use analytics to see what works:

- All items per-rent-period vs. mix of durations
- High vs. low premium on store prices
- Many small items vs. few large items
- Required vs. all-optional items

---

## Real-World Connections

### Teaching Concepts

**Itemized Rent Teaches:**
- **Bundling:** Multiple services for one price (like cable/internet packages)
- **À La Carte Pricing:** Pay only for what you use (like streaming services)
- **Value Perception:** Understanding what you're actually getting
- **Rent vs. Own:** Fixed costs for guaranteed access
- **Trade-offs:** Convenience vs. cost control

**Discussion Questions:**
- "Is it better to pay rent or buy items separately? Why?"
- "How is this like real utilities (water, electricity)?"
- "What if you only need 1-2 items - still pay rent?"
- "How do businesses use bundle pricing?"

### Real-World Examples

**Apartment Rent:**
- Unit cost ($1000)
- Water included
- Electric separate
- Internet separate
= Total housing cost higher than base rent

**Gym Membership:**
- Monthly fee ($50)
- Access to all equipment
- Classes included
- Personal training extra
= Bundle vs. paying per visit

**Streaming Services:**
- Netflix ($15/month) - all content
- Buy movies individually ($5 each)
= Bundle better if watch 4+ movies

---

## Related Documentation

- [Managing Rent Settings](managing-rent.md) - Complete rent configuration guide
- [Store Management](../store/creating-items.md) - Store item configuration
- [Economy Design Guide](../../user-guides/economy_guide.md) - Balanced economy design
- [Student Guide - Rent](../../user-guides/student_guide.md#rent) - Student perspective

---

## Feedback and Support

Have questions or suggestions about rent itemization?

- **In-App:** Help & Support → Report an Issue
- **Documentation:** [Teacher Manual](../../user-guides/teacher_manual.md)
- **Community:** Share your rent setup strategies!

---

**Last Updated:** 2026-01-09
**Version:** 1.7.0
**Feature Status:** MVP - Automatic pricing calculator coming in future release
