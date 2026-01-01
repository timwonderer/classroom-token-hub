---
title: Creating Store Items
category: store
roles: [teacher]
related:
  - features/store/managing-inventory
  - features/store/redemptions
  - user-guides/teacher_manual#store-and-rewards
---

# Creating Store Items

Learn how to create and configure store items for your classroom economy.

## What You'll Learn

- How to create basic store items
- Understanding item types (virtual vs physical)
- Setting prices and limits
- Configuring expiration dates
- Creating hall pass items

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
  - Tier 1: Low-priced items ($1-50)
  - Tier 2: Medium-priced items ($51-200)
  - Tier 3: High-priced items ($201+)

#### Item Type

Choose how the item works:

**Virtual Items** (immediate redemption):
- Student purchases, automatically "owns" it
- No teacher approval needed
- Good for: Points, privileges, digital rewards
- Example: "5 Bonus Points" - automatically added to their record

**Physical Items** (requires redemption):
- Student purchases, teacher approves redemption later
- Use for tangible rewards
- Good for: Snacks, pencils, small prizes
- Example: "Candy Bar" - student must redeem in person

**Hall Pass Items**:
- Adds to student's hall pass balance
- Used with hall pass system
- Example: "2 Extra Hall Passes"

### 3. Configure Limits (Optional)

**Purchase Limits**:
- **Daily limit**: How many times per day a student can buy this item
- **Total limit**: Maximum lifetime purchases per student
- Leave blank for unlimited purchases

**Example Limits**:
- Homework Pass: 1 per week, 4 total per semester
- Candy: 2 per day, unlimited total
- Seat Change: No daily limit, 2 total

### 4. Set Expiration (Optional)

**Expiration Date**:
- Item disappears from store after this date
- Good for seasonal items or limited-time offers
- Example: "Halloween Candy" expires Nov 1

**Expiration After Purchase**:
- Item must be redeemed within X days of purchase
- Prevents students from hoarding
- Example: "Snack" expires 7 days after purchase

### 5. Add Image (Optional)

Upload an image to make the item more appealing:
- Supported formats: JPG, PNG, GIF
- Recommended size: 400x400 pixels
- File size: Under 2MB

### 6. Save the Item

1. Click **Create Item**
2. The item is created as **Inactive** by default
3. To make it available, click **Activate** next to the item

## Item Types Explained

### Virtual Items

Best for:
- Bonus points
- Privileges (sit where you want, choose group partner)
- Digital rewards
- Automatic grade adjustments

**How they work**:
- Student clicks "Purchase"
- Tokens deducted immediately
- Item added to "My Items"
- No teacher action required

### Physical Items

Best for:
- Tangible rewards (candy, pencils, stickers)
- Items you need to hand out
- Limited quantity items

**How they work**:
- Student clicks "Purchase"
- Tokens deducted
- Item appears in **Redemptions** queue for teacher
- Teacher marks as "Redeemed" when item is given

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
3. Use virtual items for automatic multi-reward bundles

Example: "Starter Pack" ($200) includes:
- 2 Homework Passes
- 1 Seat Change
- 5 Bonus Points

### Collective Goal Items

Items the whole class contributes to:
1. Set a high price (e.g., $5000)
2. Enable "Collective Goal" option (if available)
3. Students contribute individually
4. When goal reached, whole class benefits

Example: "Pizza Party" - class collectively raises $5000

## Common Scenarios

### Scenario: Homework Pass

**Setup**:
- Name: "Homework Pass"
- Price: $150
- Type: Virtual
- Daily Limit: None
- Total Limit: 4 (per semester)
- Description: "Skip one homework assignment. Cannot be used on tests or projects. Must notify teacher before assignment is due."

### Scenario: Snack from Treasure Box

**Setup**:
- Name: "Snack"
- Price: $50
- Type: Physical
- Daily Limit: 2
- Total Limit: None
- Expiration after purchase: 7 days
- Description: "Choose one snack from the treasure box. Must redeem within one week."

### Scenario: Extra Hall Passes

**Setup**:
- Name: "2 Extra Hall Passes"
- Price: $100
- Type: Hall Pass
- Daily Limit: None
- Total Limit: None
- Hall Pass Quantity: 2
- Description: "Adds 2 passes to your hall pass balance."

## Tips for Success

- **Start simple**: Begin with 3-5 basic items
- **Balance pricing**: Use the Economy Health page to ensure prices are fair
- **Clear descriptions**: Students should understand exactly what they're buying
- **Use images**: Visual items are more appealing
- **Monitor redemptions**: Check the Redemptions tab regularly
- **Adjust as needed**: Change prices if items aren't selling or are too popular

## Troubleshooting

**Students can't see my item**:
- Check if item is Activated
- Verify Store feature is enabled in Feature Settings
- Ensure students are in the correct class period

**Item sold out too quickly**:
- Set daily or total limits
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
- [Teacher Manual: Store](/docs/user-guides/teacher_manual#store-and-rewards)

## Need More Help?

- View the complete [Teacher Manual](/docs/user-guides/teacher_manual)
- Check [Economy Health](/docs/features/payroll/economy-health) for pricing guidance
- Contact support if items aren't working as expected
