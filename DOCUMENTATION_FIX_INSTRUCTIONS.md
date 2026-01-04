# Documentation Accuracy Fix Instructions

**Created:** 2026-01-04
**Purpose:** Systematic correction of all documentation inaccuracies identified in comprehensive audit
**Total Issues:** 10 (5 Critical, 3 Major, 2 Minor)

---

## Standards & Requirements

### Documentation Standards (from CLAUDE.md)

All fixes MUST follow these requirements:

1. **Update CHANGELOG.md** - Add entry under "Unreleased" → "Documentation"
2. **Be 100% accurate** - Every claim must be verifiable in code
3. **Include code references** - Point to actual implementation when helpful
4. **Use consistent terminology** - Match code field names (e.g., "immediate" not "Virtual Items")
5. **No assumptions** - Only document what actually exists

### Verification Requirements

For each fix:
1. Read the actual code implementation
2. Verify field names, default values, and behavior
3. Test the feature if possible
4. Cross-reference related documentation

---

## CRITICAL FIXES (Priority 1)

### Fix 1: Store Tier System
**File:** `docs/features/store/creating-items.md`
**Lines:** 48-54

**Current (WRONG):**
```markdown
#### Pricing

- **Price (tokens)**: How many tokens the item costs
- **Tier**: Optional pricing tier for economy balance tracking
  - Tier 1: Low-priced items ($1-50)
  - Tier 2: Medium-priced items ($51-200)
  - Tier 3: High-priced items ($201+)
```

**Replace with (CORRECT):**
```markdown
#### Pricing

- **Price (tokens)**: How many tokens the item costs
- **Tier**: Optional pricing tier for economy balance tracking
  - No Tier (leave blank)
  - Basic (2-5% of CWI)
  - Standard (5-10% of CWI)
  - Premium (10-25% of CWI)
  - Luxury (25-50% of CWI)

> **Note:** Tiers are organizational labels based on percentage of Class Wealth Index (CWI), not fixed dollar amounts. They help you categorize items by their relative cost in your classroom economy.
```

**Verification:**
- Check `forms.py:14-19` for actual tier choices
- Check `app/models.py:572` for tier field definition

---

### Fix 2: Store Item Default State
**File:** `docs/features/store/creating-items.md`
**Lines:** 108-112

**Current (WRONG):**
```markdown
### 6. Save the Item

1. Click **Create Item**
2. The item is created as **Inactive** by default
3. To make it available, click **Activate** next to the item
```

**Replace with (CORRECT):**
```markdown
### 6. Save the Item

1. Review the **Item is Active** checkbox (checked by default)
2. If you want the item hidden from students initially, uncheck **Item is Active**
3. Click **Save Item**
4. The item will be visible to students immediately if active
5. To change visibility later, click **Activate/Deactivate** next to the item
```

**Verification:**
- Check `app/models.py:578` - `is_active = db.Column(db.Boolean, default=True, nullable=False)`
- Check `forms.py:31` - `is_active = BooleanField('Item is Active', default=True)`

---

### Fix 3: Remove Automatic Payroll Documentation
**File:** `docs/features/payroll/running-payroll.md`
**Lines:** Multiple sections

**Section 1 - Lines 31-37:**

**Current (WRONG):**
```markdown
### Prerequisites

✅ **Payroll Settings configured**:
- Pay rate set (e.g., $10/hour)
- Schedule configured (if using automatic payroll)
```

**Replace with (CORRECT):**
```markdown
### Prerequisites

✅ **Payroll Settings configured**:
- Pay rate set (e.g., $10/hour)
- Pay frequency planned (e.g., weekly, bi-weekly)
```

**Section 2 - Lines 45-51:**

**Current (WRONG):**
```markdown
Visit **Payroll** → **Settings** to verify:
- **Pay Rate**: How much students earn per hour
- **Pay Schedule**: Weekly, bi-weekly, or manual
- **Block-Specific Rates** (Advanced): Different pay for different periods
```

**Replace with (CORRECT):**
```markdown
Visit **Payroll** → **Settings** to verify:
- **Pay Rate**: How much students earn per hour
- **Block-Specific Rates** (Advanced): Different pay for different periods

> **Note:** Payroll is always run manually. There is no automatic payroll feature. Set a reminder to run payroll on your chosen schedule.
```

**Section 3 - DELETE ENTIRE SECTION (Lines 128-159):**

**Delete this entire section:**
```markdown
## Payroll Schedules

### Manual Payroll

**How it works**:
... (entire section through line 159)
```

**Replace with:**
```markdown
## Payroll Schedule Planning

**Payroll is always manual** - you must click "Run Payroll" to process payments.

### Best Practices for Consistency

**Set a recurring reminder**:
- Weekly: Every Friday at the same time
- Bi-weekly: Every other Friday
- Use your calendar app to create a recurring event

**Communicate your schedule**:
- Post your payroll day on the classroom board
- Announce before running: "Paychecks processing!"
- Be consistent so students know when to expect pay

**Tips**:
- Run payroll same day/time each week
- Run before students want to shop in the store
- Friday afternoons work well (students see earnings before weekend)
```

**Verification:**
- Check `app/routes/admin.py:4632-4709` - Only manual POST route exists
- Confirm NO automatic payroll scheduler in codebase

---

### Fix 4: Break Time Payment Clarification
**File:** `docs/features/payroll/running-payroll.md`
**Lines:** 59-77, 241-247

**Current in "What Gets Calculated" (Line 62 - WRONG):**
```markdown
1. **Calculates work time** since last payroll:
   - Looks at all "Start Work" and "Done" events
   - Calculates total minutes worked
   - Excludes break time
```

**Replace with (CORRECT):**
```markdown
1. **Calculates work time** since last payroll:
   - Looks at all "Start Work" (active tap) and "Done" (inactive tap) events
   - Calculates total minutes between active and inactive taps
   - Includes all time logged, regardless of reason
```

**Current in Q&A (Lines 246-247 - WRONG):**
```markdown
**Q: Do students on break get paid?**
A: No, break time is excluded from hours worked.
```

**Replace with (CORRECT):**
```markdown
**Q: Do students on break get paid?**
A: Yes, all time between "Start Work" and "Done" taps is paid at the configured rate. The system does not differentiate between work time and break time.
```

**Add new Q&A:**
```markdown
**Q: How can I handle breaks if I don't want to pay for them?**
A: If you want unpaid breaks, ask students to tap "Done" before breaks and "Start Work" after breaks. This creates separate paid work sessions.
```

**Verification:**
- Check `attendance.py:65-137` - calculate_unpaid_attendance_seconds function
- Check `attendance.py:94-99` - Only pairs active/inactive, no break logic

---

### Fix 5: Remove "Work & Pay" Page Reference
**File:** `docs/features/payroll/running-payroll.md`
**Lines:** 255-256

**Current (WRONG):**
```markdown
**Q: Can students see their hours before payroll runs?**
A: Yes! They can view projected earnings on their **Work & Pay** page.
```

**Replace with (CORRECT):**
```markdown
**Q: Can students see their hours before payroll runs?**
A: Students can see their attendance history on their dashboard. Projected earnings are calculated during the payroll preview before you run payroll.
```

**Verification:**
- Confirm no "Work & Pay" route exists in `app/routes/student.py`
- Confirm no "work_pay" or "payroll" student template exists

---

## MAJOR FIXES (Priority 2)

### Fix 6: Remove Daily Purchase Limits
**File:** `docs/features/store/creating-items.md`
**Lines:** 77-87

**Current (WRONG):**
```markdown
### 3. Configure Limits (Optional)

**Purchase Limits**:
- **Daily limit**: How many times per day a student can buy this item
- **Total limit**: Maximum lifetime purchases per student
- Leave blank for unlimited purchases

**Example Limits**:
- Homework Pass: 1 per week, 4 total per semester
- Candy: 2 per day, unlimited total
- Seat Change: No daily limit, 2 total
```

**Replace with (CORRECT):**
```markdown
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
```

**Additional changes in same file, Line 185-187:**

**Current (WRONG):**
```markdown
**Setup**:
- Name: "Homework Pass"
- Price: $150
- Type: Virtual
- Daily Limit: None
- Total Limit: 4 (per semester)
```

**Replace with (CORRECT):**
```markdown
**Setup**:
- Name: "Homework Pass"
- Price: $150
- Type: Immediate Use
- Inventory: Leave blank (unlimited)
- Purchase Limit per Student: 4 (can own max 4 at once)
```

**Fix other example scenarios similarly (Lines 191-210):**
- Remove all "Daily Limit" references
- Use "Inventory" and "Purchase Limit per Student" correctly
- Use actual code terminology ("Immediate Use" not "Virtual")

**Verification:**
- Check `app/models.py:574-575` - Only `inventory` and `limit_per_student` exist
- Check `forms.py:27-28` - Confirm field labels

---

### Fix 7: Remove Image Upload Documentation
**File:** `docs/features/store/creating-items.md`
**Lines:** 101-106

**Current (WRONG):**
```markdown
### 5. Add Image (Optional)

Upload an image to make the item more appealing:
- Supported formats: JPG, PNG, GIF
- Recommended size: 400x400 pixels
- File size: Under 2MB

### 6. Save the Item
```

**Replace with (CORRECT):**
```markdown
### 5. Save the Item
```

**Also update "What You'll Learn" section (Lines 15-21):**

**Current:**
```markdown
- Setting prices and limits
- Configuring expiration dates
- Creating hall pass items
```

**Replace with:**
```markdown
- Setting prices and limits
- Configuring expiration dates
- Understanding item types (immediate, delayed, collective, hall pass)
```

**Verification:**
- Check `app/models.py:565-599` - No image field in StoreItem model
- Check `forms.py:10-85` - No image field in StoreItemForm

---

### Fix 8: Remove Transfer Limits Documentation
**File:** `docs/features/banking/transferring-money.md`
**Lines:** 99-108

**Current (WRONG):**
```markdown
## Transfer Limits

### Daily Limits

Some teachers set limits on transfers:
- **Daily limit**: Maximum you can transfer per day
- **Minimum transfer**: Smallest amount allowed
- **Maximum balance**: Highest your savings can go

If limits exist, you'll see a message if you exceed them.
```

**Replace with (CORRECT):**
```markdown
## Transfer Rules

**No negative balances**:
- Cannot transfer more than your current balance
- System prevents transfers that would make balance negative
```

**Verification:**
- Check `app/models.py:1356-1398` - BankingSettings has no transfer limit fields
- Check `forms.py:304-348` - No transfer limit form fields

---

## MINOR FIXES (Priority 3)

### Fix 9: Add Collective Goal Item Type
**File:** `docs/features/store/creating-items.md`
**Lines:** 56-76

**Current (MISSING ITEM TYPE):**
```markdown
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
```

**Replace with (CORRECT):**
```markdown
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
```

**Also update "Item Types Explained" section (Lines 114-153):**

Change all "Virtual Items" to "Immediate Use"
Change all "Physical Items" to "Delayed Use"
Add new section for "Collective Goal Items"

**Add after "Hall Pass Items" section:**
```markdown
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
```

**Verification:**
- Check `forms.py:21-26` - 4 item types including 'collective'
- Check `app/models.py:590-592` - Collective goal fields exist
- Check `forms.py:45-50` - Collective goal type and target fields

---

### Fix 10: Remove "If Available" Qualifier
**File:** `docs/features/store/creating-items.md`
**Lines:** 168-176

**Current (CONFUSING):**
```markdown
### Collective Goal Items

Items the whole class contributes to:
1. Set a high price (e.g., $5000)
2. Enable "Collective Goal" option (if available)
3. Students contribute individually
4. When goal reached, whole class benefits

Example: "Pizza Party" - class collectively raises $5000
```

**Replace with (CLEAR):**
```markdown
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
```

**Verification:**
- Feature is fully implemented and production-ready
- No experimental flags or optional settings

---

## Post-Fix Verification Checklist

After making all fixes, verify:

- [ ] All 10 issues addressed
- [ ] All code references checked and accurate
- [ ] Terminology matches actual field names from forms.py
- [ ] No new inaccuracies introduced
- [ ] Related sections updated for consistency
- [ ] CHANGELOG.md updated with documentation fixes

---

## CHANGELOG Entry Template

Add to `CHANGELOG.md` under `## [Unreleased]` → `### Documentation`:

```markdown
### Documentation

#### Fixed
- **Store Items:** Corrected tier system documentation to reflect actual implementation (percentage of CWI, not dollar amounts)
- **Store Items:** Fixed incorrect default state - items are active by default, not inactive
- **Store Items:** Removed non-existent image upload feature from documentation
- **Store Items:** Removed non-existent daily purchase limit from documentation
- **Store Items:** Added missing "Collective Goal" item type to documentation
- **Store Items:** Clarified "if available" language for collective goals (feature is fully available)
- **Store Items:** Updated terminology to match code (Immediate/Delayed instead of Virtual/Physical)
- **Store Items:** Corrected purchase limits documentation to reflect actual behavior (concurrent ownership)
- **Payroll:** Removed non-existent automatic payroll feature from documentation
- **Payroll:** Clarified that break time IS paid (system does not exclude breaks)
- **Payroll:** Removed non-existent "Work & Pay" page reference
- **Banking:** Removed non-existent transfer limits from documentation

#### Improved
- **Store Items:** Enhanced item type explanations with clearer examples
- **Payroll:** Added guidance for manual payroll scheduling and consistency
- **Store Items:** Clarified purchase limit behavior (can buy again after use)
```

---

## Files to Modify

**Summary of files requiring changes:**

1. `docs/features/store/creating-items.md` - 7 fixes (Issues #1, 2, 6, 7, 9, 10)
2. `docs/features/payroll/running-payroll.md` - 3 fixes (Issues #3, 4, 5)
3. `docs/features/banking/transferring-money.md` - 1 fix (Issue #8)
4. `CHANGELOG.md` - 1 update (add documentation fixes)

**Total:** 4 files

---

## Completion Criteria

Documentation is considered fixed when:

1. ✅ All 10 documented issues are corrected
2. ✅ Every field name matches actual code implementation
3. ✅ Every default value matches actual code
4. ✅ No features documented that don't exist
5. ✅ All existing features are documented
6. ✅ Terminology is consistent (code names vs. user-friendly descriptions)
7. ✅ CHANGELOG.md is updated
8. ✅ All code references point to correct files/lines
9. ✅ Documentation can be verified by reading the code
10. ✅ A stressed user with a broken feature can find accurate help

---

**Last Updated:** 2026-01-04
**Audit Report:** See comprehensive audit report for full details and code references
