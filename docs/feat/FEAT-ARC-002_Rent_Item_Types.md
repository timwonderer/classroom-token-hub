# Rent Item Types Implementation Plan

**Feature:** Rent Item Type Extension (Privilege / Per-Use / Hall Pass)
**Date:** 2026-02-06
**Status:** Implementation complete

---

## Overview

This feature extends the existing itemized rent system by adding three distinct **item types** to each rent item. Currently, rent items have a simple store integration with `is_available_in_store` and `purchase_duration` (per_use/per_period). This extension replaces that with a richer type system that drives different behaviors for each rent item.

---

## Three Item Types

### 1. Privilege (Badge/Monthly Pass)

**Behavior:** When a student pays rent, they receive a badge on the teacher's roster for each privilege item. This is essentially a "monthly pass" — paying rent grants the privilege for the rent period.

**Store integration:**

- Teacher can **optionally** toggle whether this privilege is listed in the store
- If listed, teacher sets a price
- A student who purchases the privilege from the store gets the **same badge** on the roster as one who got it through rent
- Badge colors remain: green = rent-covered, blue = individually purchased

**This is closest to the current `per_period` behavior**, just explicitly labeled.

### 2. Per-Use Item

**Behavior:** Paying rent grants the student a quota of free uses (store redemptions) rather than a permanent badge.

**Key rules:**

- **Must always be listed in the store** (students redeem their free uses there)
- Paying rent grants free uses up to the limit (default single-use if left empty)
- Teacher can set a number of free uses per rent period (e.g., 5)
- Store item shows a **"Rent Perk"** badge/label in the store UI
- **Cannot be deleted from the store** — only removable by deleting the rent item itself
- Teacher sees an alert: "You can customize this item in the store later (immediate, delayed, etc.)"
- Free uses are tracked per student, per period

### 3. Hall Pass

**Behavior:** Paying rent tops off the student's hall pass count (rent-granted portion only).

**Key rules:**

- Teacher enters how many hall passes to grant per rent period
- System uses a **top-off** model that tracks rent-granted vs. purchased passes separately
- **Top-off logic:**
  - Only replenishes the rent-granted portion back to the specified amount
  - Purchased passes are never touched
  - Example: Rent grants 3. Student has 1 rent + 2 purchased = 3 total. Top-off adds 2 → 3 rent + 2 purchased = 5 total
- **Store deduplication:** System checks if a hall pass already exists in the store (by `item_type='hall_pass'`). If yes, don't create a new one. If no, teacher can opt to list one.

---

## Data Model Changes

### Modified Models

#### `RentItem` — New fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `rent_item_type` | `String(20)` | `'privilege'` | Item type: `'privilege'`, `'per_use'`, or `'hall_pass'` |
| `use_limit` | `Integer` | `NULL` | For per_use: number of free uses per period. NULL = single-use |
| `hall_pass_count` | `Integer` | `NULL` | For hall_pass: number of passes to grant/top-off per period |

**Notes:**

- `rent_item_type` defaults to `'privilege'` for backward compatibility (existing items behave as privileges)
- The existing `is_available_in_store`, `store_price`, `purchase_duration`, and `store_item_id` fields remain and are used by privilege and per_use types

#### `StoreItem` — New field

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `is_rent_linked` | `Boolean` | `False` | If true, item cannot be deleted from store (only via rent settings) |

**Notes:**

- Set to `True` when a per_use rent item creates a store item
- Prevents accidental deletion that would break the rent ↔ store relationship
- Store deletion routes will check this flag and block deletion with an error message

#### `StudentBlock` — New field

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `rent_hall_passes` | `Integer` | `0` | Tracks how many of the student's hall passes came from rent (for top-off calculation) |

**Notes:**

- Used alongside `Student.hall_passes` (total passes from all sources)
- When a pass is used: decrement `Student.hall_passes` by 1, and if `rent_hall_passes > 0` decrement it too (rent passes consumed first)
- Top-off calculation: `top_off_amount = hall_pass_count - rent_hall_passes`, add that to `Student.hall_passes`, set `rent_hall_passes = hall_pass_count`

### Per-Use Tracking

Per-use free uses are tracked directly on `StudentItem.uses_remaining` for rent-granted items.

**Notes:**

- Created when a student pays rent and the rent has per_use items
- `uses_remaining` is decremented each time the student "purchases" the linked store item for free
- When `uses_remaining` reaches 0, the student pays regular price for subsequent purchases
- If `use_limit` is NULL on the rent item, treat it as **single-use** and initialize `uses_remaining = 1`

---

## Route Changes

### Rent Item Edit Guardrail (Mid-Period Lock)

**Rule:** If at least one student has successfully paid rent for the current coverage period, rent item *type semantics* are immutable until the next period.

**Enforced at:**

- `POST /admin/rent-settings`

**Blocked or deferred changes:**

- Changing `rent_item_type`
- Modifying `use_limit`
- Modifying `hall_pass_count`

**Allowed mid-period changes:**

- Display name and description
- Store price (affects only paid purchases, not rent-granted uses)
- Store listing visibility (for privilege items only)

**Implementation note:**

- The backend should detect paid rent records for the current join_code + period.
- If detected, semantic changes are saved as pending configuration and applied when the period rolls over.
- Alternatively (simpler v1): block submission and require confirmation that changes apply next period only.

### Admin Routes (`app/routes/admin.py`)

#### `POST /admin/rent-settings`

**Rent item form parsing** — New fields per item:

- `rent_item_type_{index}`: `'privilege'` | `'per_use'` | `'hall_pass'`
- `rent_item_use_limit_{index}`: Integer (for per_use; leave blank for single-use)
- `rent_item_hall_pass_count_{index}`: Integer (for hall_pass)
- `rent_item_hall_pass_list_in_store_{index}`: Checkbox (for hall_pass, opt to list in store)

**Logic changes:**

- When `rent_item_type = 'per_use'`:
  - Force `is_available_in_store = True` (always listed)
  - Set `use_limit` from form (NULL = single-use)
- When `rent_item_type = 'hall_pass'`:
  - Set `hall_pass_count` from form
  - Check if hall pass already exists in store (by `item_type='hall_pass'` for this teacher)
  - If not exists and teacher opts in, create hall pass store item
  - Do NOT create a linked store item via `_sync_rent_items_to_store` (hall pass top-off is separate from store)
- When `rent_item_type = 'privilege'`:
  - Existing behavior: optional store listing, price, purchase_duration

#### `_sync_rent_items_to_store()`

**Changes:**

- For `per_use` items: always create store item, set `is_rent_linked = True`
- For `privilege` items: existing behavior (create if `is_available_in_store`)
- For `hall_pass` items: skip store sync (handled separately)
- When deactivating a store item linked to per_use: only deactivate if rent item is removed

#### Store deletion routes

**`POST /admin/store/delete/<item_id>`** and **`POST /admin/store/hard-delete/<item_id>`**:

- Check `store_item.is_rent_linked`
- If true: flash error "This item is linked to rent and can only be removed from Rent Settings" and redirect
- Block both soft and hard delete

#### `_build_rent_privileges_by_block()` and `_get_rent_privileges_for_student()`

**Changes:**

- For `privilege` items: existing behavior (show badge with source)
- For `per_use` items: show "Rent Perk" in store, NOT as a roster badge (per_use items display their badge in the store, not roster)
- For `hall_pass` items: not shown as a privilege badge (hall passes are shown separately in the hall pass column)

### Student Routes (`app/routes/student.py`)

#### `POST /student/rent/pay/<period>`

After successful rent payment, add:

1. **Per-use grants:** For each `per_use` rent item, create a `StudentItem` with `uses_remaining = use_limit` (or `1` if `use_limit` is NULL)
2. **Hall pass top-off:** For each `hall_pass` rent item:
   - Get `StudentBlock.rent_hall_passes` for this join_code
   - Calculate `top_off = hall_pass_count - rent_hall_passes`
   - If `top_off > 0`: add to `Student.hall_passes`, set `rent_hall_passes = hall_pass_count`

### API Routes (`app/routes/api.py`)

#### `POST /api/purchase-item`

**Changes for per_use rent items:**

- When a student purchases a store item that is `is_rent_linked`:
  - Check for an active `StudentItem` for this student + join_code with `uses_remaining > 0`
  - If a free-use item exists: purchase is **free** (price = 0), decrement `uses_remaining`
  - If no free-use item or uses exhausted: charge regular store price
- The "Rent Perk" badge in the store UI indicates the item has free uses from rent

**Changes for hall pass purchases:**

- Existing behavior: increments `Student.hall_passes`
- No change needed here — purchased passes are separate from rent passes
- The `rent_hall_passes` tracking on StudentBlock is not affected by store purchases

### Hall Pass Usage

Wherever hall passes are decremented (in hall pass routes):

- Decrement `Student.hall_passes` by 1
- If the student's `StudentBlock.rent_hall_passes > 0` for the current join_code, decrement it by 1 too
- This ensures rent-granted passes are consumed first, preserving purchased passes

---

## Template Changes

### `admin_rent_settings.html`

**Per rent item card — replace existing store integration fields with:**

1. **Item Type selector** (radio buttons or dropdown):
   - Privilege (Badge)
   - Per-Use Item
   - Hall Pass

2. **Conditional fields based on type:**

   **Privilege:**

   - [ ] List in Store (checkbox)
   - Price field (shown when store listing enabled)
   - Purchase duration radio (per_use / per_period) — existing behavior

   **Per-Use:**

   - Alert: "This item will be listed in the store. You can customize item details in the store later."
   - Price field (store price for when free uses are exhausted)
   - Use limit input (leave blank for single-use)

   **Hall Pass:**

   - Number of hall passes to grant per rent period
   - Info: shows whether hall pass already exists in store
   - [ ] List hall pass in store (only shown if no hall pass exists in store)

### `student_shop.html`

**Store item display changes:**

- If store item has `is_rent_linked = True`: show a **"Rent Perk"** badge on the item card
- If student has an active rent-granted `StudentItem` with `uses_remaining`: show "X free uses remaining"
- If no free-use item or uses exhausted: show regular price

### `admin_students.html` (Roster)

**Privilege badge column:**

- Only `privilege`-type rent items appear as badges (existing behavior)
- `per_use` items do NOT appear as roster badges (they show "Rent Perk" in store instead)
- `hall_pass` items do NOT appear as roster badges (hall passes shown in their own column)

### `admin_store.html`

**Store item list:**

- Items with `is_rent_linked = True`: show "Rent Perk" badge and disable delete button
- Tooltip on disabled delete: "Remove from Rent Settings to delete"

---

## Migration

**Name:** `add_rent_item_types_and_allocation` + `add_uses_remaining_to_student_item`

**Upgrade operations:**

1. Add `rent_item_type` column to `rent_items` (default `'privilege'`)
2. Add `use_limit` column to `rent_items` (nullable)
3. Add `hall_pass_count` column to `rent_items` (nullable)
4. Add `is_rent_linked` column to `store_items` (default `False`)
5. Add `rent_hall_passes` column to `student_blocks` (default `0`)
6. Add `uses_remaining` column to `student_items`

**Data migration:**

- Existing rent items get `rent_item_type = 'privilege'` (default, no action needed)
- Existing per_period items remain as privileges (closest match)
- No existing data needs transformation

**Downgrade operations:**

- Drop `uses_remaining` column from `student_items`
- Drop added columns from `rent_items`, `store_items`, `student_blocks`

---

## Testing Plan

### Unit Tests

1. **Model tests:**
   - RentItem creation with each type
   - StudentItem `uses_remaining` tracking
   - StudentBlock.rent_hall_passes tracking

2. **Privilege type tests:**
   - Privilege badge appears on roster when rent paid
   - Privilege badge appears when purchased from store
   - Store listing optional

3. **Per-use type tests:**
   - Store item auto-created with `is_rent_linked = True`
   - Allocation created on rent payment
   - Free purchase when `uses_remaining` exists
   - Regular price when `uses_remaining` is exhausted
   - Single-use when `use_limit` is NULL
   - Cannot delete rent-linked store item
   - Can delete after removing from rent settings

4. **Hall pass type tests:**
   - Top-off logic: rent-granted portion replenished
   - Purchased passes preserved during top-off
   - Hall pass store deduplication (no duplicate creation)
   - Optional store listing when no hall pass exists

5. **Multi-tenancy tests:**
   - Per-use tracking scoped by join_code
   - Hall pass top-off scoped by join_code
   - Per-use tracking per class period

6. **Integration Tests**
   - Full rent payment flow with mixed item types
   - Store purchase flow with rent free-use checking
   - Hall pass usage with rent-granted tracking
   - Rent settings update — changing item types, removing items

10. **Mid-period edit guardrail tests:**  
   - Editing rent item type after rent payment shows warning and does not alter current free-use grants  
   - Changes apply correctly on next period rollover

---

## Edge Cases

1. **Teacher changes item type after students paid rent:**  
   Once rent has been paid for a given coverage period (month/year), the `rent_item_type` and its type-specific fields (`use_limit`, `hall_pass_count`) are **locked for that period**.  

   - Existing free-use grants, privileges, and hall pass top-offs remain valid until the period ends.  
   - Any changes made in Rent Settings are queued and only take effect starting with the **next rent period**.  
   - Admin UI should display a warning banner when editing a rent item mid-period:  
     > 'Changes will apply starting next rent period. Current students’ rent benefits will not be altered.'

2. **Student has single-use per-use item but teacher later changes to multi-use:** Current period keeps single-use. Next period uses new limit.
3. **Hall pass top-off when student has 0 passes:** Simply grants the full `hall_pass_count`.
4. **Incremental rent payment with per-use items:** Allocations are only created when rent is **fully paid** for the period.
5. **Apply to all blocks:** Item type and settings sync across all blocks (same as current name/price sync behavior).
