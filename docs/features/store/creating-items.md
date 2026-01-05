---
title: Creating Store Items
category: store
roles: [teacher]
description: Create and configure store items like rewards, privileges, and hall passes for your classroom economy.
keywords: [store, items, rewards, privileges, shop, inventory, hall pass, collective goals, purchases]
related:
  - features/store/managing-inventory
  - features/store/redemptions
  - diagnostics/teacher-store
---

# Creating Store Items

Learn how to create and configure store items for your classroom economy.

## What You'll Learn

- How to create basic store items
- Understanding item types (immediate, delayed, collective, hall pass)
- Setting prices and limits
- Configuring expiration dates
- Creating collective goal items

## Before You Start

Make sure the Store feature is enabled in your Feature Settings. Navigate to **Settings** → **Feature Settings** and ensure "Store" is checked.

## Step-by-Step Guide

### 1. Navigate to Store Management

From the admin dashboard:
1. Click **Store** in the sidebar
2. You'll see the Store Management page with tabs for **Manage Items** and **Redemptions**

### 2. Create a New Item

1. Click the **+ Add Item** button (top right)
2. Fill in the item details:

#### Basic Information

- **Item Name**: What students see (e.g., "Homework Pass", "Extra Credit")
- **Description**: Explain what the item does
  - Use markdown for formatting
  - Be clear about any restrictions
  - Example: "Skip one homework assignment (cannot be used on tests)"

#### Pricing

- **Price (tokens)**: How many tokens the item costs
- **Tier**: Optional pricing tier for economy balance tracking
  - No Tier (leave blank)
  - Basic (2-5% of CWI)
  - Standard (5-10% of CWI)
  - Premium (10-25% of CWI)
  - Luxury (25-50% of CWI)

> **Note:** Tiers are organizational labels based on percentage of Class Wealth Index (CWI), not fixed dollar amounts. They help you categorize items by their relative cost in your classroom economy.

#### Item Type

Choose how the item works:

**Immediate Use**:
- Student purchases, automatically "owns" it
- No teacher approval needed
- Status changes to "completed" immediately
- Good for: Bonus points, privileges, digital rewards
- Example: "5 Bonus Points" - automatically added to their record

**Delayed Use**:
- Student purchases, teacher approves redemption later
- Status is "processing" until teacher marks as redeemed
- Use for tangible rewards you hand out
- Good for: Snacks, pencils, small prizes
- Example: "Candy Bar" - student must redeem in person

**Collective Goal**:
- Class works together to reach a purchase goal
- Choose "Fixed Number" (set target) or "Whole Class" (everyone must buy)
- Status is "pending" until goal is met
- Good for: Class rewards, pizza parties, field trips
- Example: "Pizza Party" - set goal of 20 purchases, class works together

**Hall Pass**:
- Adds passes to student's hall pass balance
- No approval needed, automatic
- Used with hall pass system
- Example: "2 Extra Hall Passes" - adds 2 to their balance

> **Note:** Item type cannot be changed after creation. Choose carefully.

### 3. Configure Limits (Optional)

**Inventory** (global stock limit):
- Total quantity available to ALL students across all periods
- Example: Set to 10 if you only have 10 physical candy bars
- Leave blank for unlimited inventory

**Purchase Limit per Student** (how many each student can own at once):
- Maximum number a student can have in their inventory at one time
- Students can buy again after using/redeeming the item
- Example: Homework Pass set to 2 means students can own max 2 at once
- Leave blank for unlimited per student

**Example Limits**:
- Homework Pass: Purchase limit 4 (max 4 at once, can buy more after using)
- Candy: Inventory 20 (only 20 total available), Purchase limit 2 (max 2 per student at once)
- Seat Change: No inventory limit, Purchase limit 2 (max 2 owned at once)

> **Note:** There is no daily purchase limit. Limits are based on concurrent ownership (how many they can have at once) and total inventory (how many exist).

### 4. Set Expiration (Optional)

**Expiration Date**:
- Item disappears from store after this date
- Good for seasonal items or limited-time offers
- Example: "Halloween Candy" expires Nov 1

**Expiration After Purchase**:
- Item must be redeemed within X days of purchase
- Prevents students from hoarding
- Example: "Snack" expires 7 days after purchase

### 5. Save the Item

1. Review the **Item is Active** checkbox (checked by default)
2. If you want the item hidden from students initially, uncheck **Item is Active**
3. Click **Save Item**
4. The item will be visible to students immediately if active
5. To change visibility later, click **Activate/Deactivate** next to the item

## Item Types Explained

### Immediate Use Items

Best for:
- Bonus points
- Privileges (sit where you want, choose group partner)
- Digital rewards
- Automatic grade adjustments

**How they work**:
- Student clicks "Purchase"
- Tokens deducted immediately
- Item added to "My Items"
- Status automatically set to "completed"
- No teacher action required

### Delayed Use Items

Best for:
- Tangible rewards (candy, pencils, stickers)
- Items you need to hand out
- Limited quantity items

**How they work**:
- Student clicks "Purchase"
- Tokens deducted
- Item appears in **Redemptions** queue for teacher
- Status is "processing"
- Teacher marks as "Redeemed" when item is given

### Collective Goal Items

Best for:
- Class-wide rewards
- Team goals
- Special events (pizza parties, movie days)
- Building class unity

**How they work**:
- **Fixed Number**: Set a target number of purchases (e.g., 20)
  - Each student who purchases contributes to the goal
  - When target is reached, all contributors benefit
  - Example: "Pizza Party" - 20 students must purchase

- **Whole Class**: Every enrolled student must purchase
  - Ensures everyone participates
  - Goal met when all students have purchased
  - Example: "Field Trip Fund" - everyone must contribute

**Status tracking**:
- Purchase status shows "pending" until goal is met
- Teacher can view progress toward goal
- When goal reached, status changes to "completed"

### Hall Pass Items

Best for:
- Extra hall pass allowance
- Restroom pass bundles

**How they work**:
- Student purchases item
- Hall passes automatically added to their balance
- Student can use passes via dashboard

## Advanced Features

### Bundle Items

Create items that give multiple rewards:
1. Set the price for the bundle
2. In description, list what's included
3. Use immediate use items for automatic multi-reward bundles

Example: "Starter Pack" ($200) includes:
- 2 Homework Passes
- 1 Seat Change
- 5 Bonus Points

### Collective Goal Items

Items the whole class works toward together:
1. Select "Collective Goal" as the item type
2. Choose goal type:
   - **Fixed Number**: Set target number of purchases (e.g., 20 students)
   - **Whole Class**: All enrolled students must purchase
3. Set the price (what each student pays)
4. Students purchase individually
5. When goal is met, all contributors benefit

**Example: Fixed Number**
- Item: "Pizza Party"
- Price: $50 per student
- Goal Type: Fixed Number
- Target: 20 purchases
- When 20 students have purchased, goal is met

**Example: Whole Class**
- Item: "Movie Day"
- Price: $100 per student
- Goal Type: Whole Class
- All students must purchase
- When everyone has contributed, class earns movie day

## Common Scenarios

### Scenario: Homework Pass

**Setup**:
- Name: "Homework Pass"
- Price: $150
- Type: Immediate Use
- Inventory: Leave blank (unlimited)
- Purchase Limit per Student: 4 (can own max 4 at once)
- Description: "Skip one homework assignment. Cannot be used on tests or projects. Must notify teacher before assignment is due."

### Scenario: Snack from Treasure Box

**Setup**:
- Name: "Snack"
- Price: $50
- Type: Delayed Use
- Inventory: 30 (only 30 snacks available)
- Purchase Limit per Student: 2 (max 2 at once)
- Expiration after purchase: 7 days
- Description: "Choose one snack from the treasure box. Must redeem within one week."

### Scenario: Extra Hall Passes

**Setup**:
- Name: "2 Extra Hall Passes"
- Price: $100
- Type: Hall Pass
- Inventory: Leave blank (unlimited)
- Purchase Limit per Student: Leave blank (unlimited)
- Description: "Adds 2 passes to your hall pass balance."

## Tips for Success

- **Start simple**: Begin with 3-5 basic items
- **Balance pricing**: Use the Economy Health page to ensure prices are fair
- **Clear descriptions**: Students should understand exactly what they're buying
- **Monitor redemptions**: Check the Redemptions tab regularly
- **Adjust as needed**: Change prices if items aren't selling or are too popular

## Troubleshooting

**Students can't see my item**:
- Check if item is Activated
- Verify Store feature is enabled in Feature Settings
- Ensure students are in the correct class period

**Item sold out too quickly**:
- Set inventory limits (total stock available)
- Set purchase limits per student (max they can own at once)
- Increase the price
- Create similar items to distribute demand

**Students aren't buying anything**:
- Prices might be too high (check Economy Health)
- Items might not be appealing (ask for student input)
- Students might be saving for something specific

## Related Articles

- [Managing Store Inventory](/docs/features/store/managing-inventory)
- [Processing Redemptions](/docs/features/store/redemptions)
- [Economy Health & Pricing](/docs/features/payroll/economy-health)
- [Teacher Diagnostics: Store](/docs/diagnostics/teacher-store)

## Need More Help?

- View the [Teacher Diagnostics Index](/docs/diagnostics/teacher)
- Check [Economy Health](/docs/features/payroll/economy-health) for pricing guidance
- Contact support if items aren't working as expected
