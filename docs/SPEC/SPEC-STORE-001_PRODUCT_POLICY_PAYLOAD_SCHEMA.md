# SPEC-STORE-001: Store Product Policy Payload Schema

| Reference Number | Version | Effective Date | Authority Level |
|------------------|---------|----------------|-----------------|
| SPEC-STORE-001 | 1.2 | 2026-09-13 | Normative |

## I. Purpose

Define the JSON schema for `STORE_PRODUCT` policy payloads consumed by Store & Entitlements FEATs.

This specification is the authoritative contract for parsing and validating product configuration when creating entitlements.

## II. Scope

This specification applies to:

- All product policies stored in `policy_versions` with `policy_family="STORE_PRODUCT"`
- All FEAT operations that read and consume product policies (FEAT-STOR-001, FEAT-STOR-004, etc.)
- All parsers, validators, and configuration objects that process product policies

## III. Authority Level

Normative. This specification is subordinate to:

- `DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- `DOM-POL-001_POLICIES_DOMAIN.md`
- `DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`

## III.A. Schema Governance Rule

**A JSON field has no contractual meaning unless it is explicitly defined by this SPEC.**

This is the controlling rule. It prevents JSON storage from becoming an escape hatch that allows callers or future features to invent arbitrary fields.

Consequences:

1. **Only declared fields are valid.** Every field in a payload MUST be enumerated in this document.
2. **Unknown fields MUST be rejected.** Parsers SHALL treat unknown fields as a validation failure (fail-fast). Silently accepting unknown fields is prohibited.
3. **Field changes require SPEC amendment.** Adding, removing, renaming, or changing the semantics or type of a field requires:
   - Amendment of this SPEC document with new version number and effective date
   - Corresponding update to all parser/validator implementations
   - Migration guidance if existing policies must be upgraded
4. **No inference of structure.** Callers and consumers MUST NOT persist or assume undeclared fields, even if "it makes sense" for a future use case.

This approach provides JSON storage flexibility (fields can change) without surrendering schema governance (arbitrary fields cannot appear).

## IV. JSON Schema

### A. Required Fields

```json
{
  "product_id": <integer>,
  "is_purchasable": <boolean>,
  "supports_direct_grants": <boolean>,
  "price": <decimal string>,
  "entitlement_type": <enum>,
  "economic_role": <enum>
}
```

**Field Definitions:**

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `product_id` | integer | Stable product identifier | Must match policy_id in policy_versions |
| `is_purchasable` | boolean | Can students purchase this product? | Required for FEAT-STOR-001 validation |
| `supports_direct_grants` | boolean | Can teachers grant directly? | Required for FEAT-STOR-004 validation |
| `price` | decimal (string) | Cost per unit | Must be ≥ 0; decimal with 2 scale |
| `entitlement_type` | enum | Entitlement lifecycle type | See Section IV.B for valid values |
| `economic_role` | enum | Required Store economic role | One of `necessity`, `convenience`, `add_on`; advisory only (see Section IV.D) |

### B. Entitlement Type Values

Closed enum; exactly one of:

```
IMMEDIATE_USE     - Granted and consumed in the same action (no expiry)
DELAYED_USE       - Granted now, consumed later (requires auto_expiry_days)
HALL_PASS         - Teacher-grantable; externally consumed by Productivity domain
PRIVILEGE         - Non-counted state (e.g., seat selection); expires by revocation only
INSURANCE         - Recurring premium liability (coordinates with Obligations)
COLLECTIVE_GOAL   - Threshold/deadline purchase (group goal completion)
```

### C. Optional Fields

```json
{
  "item_type": <enum | null>,
  "holding_limit": <integer | null>,
  "inventory_total": <integer | null>,
  "rent_grant_quantity": <integer | null>,
  "direct_purchase_allowed": <boolean>,
  "available_with_overdue_obligations": <boolean | null>,
  "rent_linked": <boolean>,
  "activation_at": <ISO8601 datetime | null>,
  "auto_delist_date": <ISO8601 datetime | null>,
  "auto_expiry_days": <integer | null>,
  "redemption_prompt": <string | null>,
  "name": <string | null>,
  "description": <string | null>,
  "bypass_cwi_warnings": <boolean>,
  "is_long_term_goal": <boolean>,
  "bundle_quantity": <integer | null>,
  "bulk_discount_quantity": <integer | null>,
  "bulk_discount_percentage": <float | null>,
  "collective_goal_type": <string | null>,
  "collective_goal_target": <integer | null>,
  "collective_goal_expires_at": <ISO8601 datetime | null>
}
```

**Field Definitions:**

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `item_type` | enum \| null | Persisted catalog type the teacher selects; `entitlement_type` is derived from it | One of `immediate`, `delayed`, `hall_pass`, `privilege`, `collective`. Required at product creation; a payload consumed by a FEAT carries the derived `entitlement_type` instead. See Section IV.D |
| `holding_limit` | int \| null | Absolute maximum active entitlements held by one student, regardless of acquisition source | Required for countable products; if set, must be > 0 |
| `inventory_total` | int \| null | Configured ceiling on units the product may ever grant | If set, must be > 0; null = unlimited. Configuration, not a balance — units remaining are derived, never persisted |
| `rent_grant_quantity` | int \| null | Number of entitlements attempted by a qualifying rent event | Required when `rent_linked` is true; if set, must be > 0 |
| `direct_purchase_allowed` | boolean | Whether a student may acquire the product through direct Store purchase | Required; independent of rent linkage |
| `available_with_overdue_obligations` | boolean \| null | Whether this product is permitted under `SPECIFIED_ITEMS_ONLY` | Required only for products subject to the specified-item policy; does not restrict rent grants |
| `rent_linked` | boolean | Whether qualifying rent may grant this product | If true, rent-grant rules below apply |
| `activation_at` | datetime \| null | When the product first becomes sellable | ISO8601; null = sellable as soon as its version is `IN_USE` |
| `auto_delist_date` | datetime \| null | When the product stops being offered | ISO8601; null = no scheduled delisting. MUST NOT be used as a rent-linked entitlement's termination mechanism |
| `auto_expiry_days` | int \| null | Days until entitlement expires | If set, must be > 0; null = never expires |
| `redemption_prompt` | string \| null | Prompt shown to the student at redemption | DELAYED_USE and HALL_PASS only; informational |
| `name` | string \| null | Display name (UI only) | Max 100 chars; informational only |
| `description` | string \| null | Product description (UI only) | Informational only |
| `bypass_cwi_warnings` | boolean | Override CWI balance warnings? | Default: false |
| `is_long_term_goal` | boolean | Exclude from CWI balance checks? | Default: false |
| `bundle_quantity` | int \| null | Items in bundle | If set, must be > 1; DELAYED_USE and HALL_PASS only; mutually exclusive with collective_goal |
| `bulk_discount_quantity` | int \| null | Min quantity for discount | If set, must be > 1; IMMEDIATE_USE, DELAYED_USE, and HALL_PASS may use bulk discounts |
| `bulk_discount_percentage` | float \| null | Discount percentage | Range: 0-100; paired with bulk_discount_quantity |
| `collective_goal_type` | string \| null | Goal threshold type | Values: "fixed" or "whole_class"; mutually exclusive with bundle fields |
| `collective_goal_target` | int \| null | Required purchases for goal | If set, must be > 0; requires collective_goal_type and collective_goal_expires_at |
| `collective_goal_expires_at` | datetime \| null | Deadline for goal completion | ISO8601 format; required if collective_goal_type is set |

### D. Persisted Inputs vs Derived Projections

Some declared fields are configured by the teacher and stored; others are
projected from a stored field at read time. Both are declared here, because
Section III.A governs the payload surface as a whole, but only a persisted
input may be written.

| Derived field | Projected from | Rule |
|---------------|----------------|------|
| `entitlement_type` | `item_type` | The catalog vocabulary is closed. An `item_type` with no mapping is a validation failure for the whole class, not a skipped row |
| `is_purchasable` | `item_type` + availability + `direct_purchase_allowed` | Never written directly |
| `supports_direct_grants` | `entitlement_type` | Never written directly |

**`economic_role` is advisory.** It is configuration guidance for the teacher
and the input to the Store CWI Helper projection required by
`SPEC-ECON-003` §4.7 and §4.9. Per `DOM-STORE-001` §XII it does not reclassify
a product, change its configured price, create a new acquisition path, or
authorize a purchase. In particular, a role of `necessity` does not itself
permit purchase while the overdue-obligation gate is active — that permission
is carried solely by `available_with_overdue_obligations` under the class
`SPECIFIED_ITEMS_ONLY` policy. A teacher is expected, but not required, to
align the two.

## V. Validation Rules

### A. Type-Specific Rules

Bundling is the narrowest of these rules, so it is stated once rather than
repeated per type: **only DELAYED_USE and HALL_PASS may be bundled.** A bundle
grants `bundle_quantity` independent entitlement lifecycles from one charge, so
it is only meaningful for a type that can hold more than one unexercised unit.
IMMEDIATE_USE is exercised at the moment of sale and PRIVILEGE is a single
standing state, so neither has units to hold; COLLECTIVE_GOAL is excluded for a
different reason, given below.

**IMMEDIATE_USE:**
- `auto_expiry_days` MUST be null (or will be ignored)
- Cannot be bundled or part of collective goal
- MAY use a bulk discount; the discount changes the price of a single immediate-use transaction

**Acquisition and holding rules:**
- `holding_limit` is the absolute post-acquisition cap across all lawful acquisition sources.
- `direct_purchase_allowed` controls only student-initiated Store purchase.
- A lawful grant MUST satisfy `on_hand + grant_quantity ≤ holding_limit` when a holding limit applies.
- A failed rent-linked grant does not itself reverse or invalidate the qualifying rent outcome; rent satisfaction and entitlement grant are separate coordinated results.

**Rent-linked products:**
- `rent_linked` MUST be true when `rent_grant_quantity` is set.
- A rent-linked entitlement's expiration boundary is derived from the applicable rent cycle and is not independently configurable through Store.
- A rent-linked product MUST NOT use Store auto-delist as its entitlement termination mechanism.
- A product that is not rent-linked is always directly purchasable; the teacher-facing direct-purchase choice is only meaningful when `rent_linked` is true.
- For a rent-linked product, `direct_purchase_allowed` remains independently configurable.
- The class-level overdue purchase policy (`ALL_ITEMS`, `SPECIFIED_ITEMS_ONLY`, or `NO_ITEMS`) is read from its owning domain through the lawful FEAT coordination path. It is not copied into product payload or Store/Entitlements state.
- The overdue purchase policy applies only to direct Store purchase and MUST NOT block a lawful rent-triggered grant.

**DELAYED_USE:**
- `auto_expiry_days` optional but recommended (null = perpetual entitlement)
- MAY be bundled; a purchase of `quantity` writes `quantity × bundle_quantity`
  `GRANTED` events, each its own lifecycle, all sharing the purchase's
  `correlation_id`. The debit is per pack, not per unit.
- Cannot be part of a collective goal

**HALL_PASS:**
- `supports_direct_grants` MUST be true
- `auto_expiry_days` optional
- MAY be bundled, on the same terms as DELAYED_USE
- Cannot be part of a collective goal

**PRIVILEGE:**
- `auto_expiry_days` is required for direct purchase and determines purchased expiry
- rent grants expire at the applicable rent-cycle boundary
- holding limit is hard-set to 1
- `supports_direct_grants` MUST be true
- Cannot be bundled or part of collective goal

**INSURANCE:**
- Recurring premium product
- `price` is per premium cycle
- `auto_expiry_days` typically null (managed by Obligations bill cycles)
- Additional insurance-specific fields (see SPEC-OBL-001)
- **Not sold through the store.** Enrollment is purchased through the insurance
  interface under FEAT-CLASS-003, not through the store purchase command, so
  the store's bundle and bulk-discount rules never reach it.

**COLLECTIVE_GOAL:**
- `collective_goal_type` MUST be set ("fixed" or "whole_class")
- `collective_goal_target` MUST be > 0
- `collective_goal_expires_at` MUST be valid future datetime
- Bundle fields MUST all be null
- Cannot coexist with bundle/bulk discount

### B. Mutual Exclusion Rules

1. **Bundle XOR Collective Goal**
   - If any of `bundle_quantity`, `bulk_discount_quantity`, `bulk_discount_percentage` is set, all collective_goal fields MUST be null
   - If any collective_goal field is set, all bundle fields MUST be null
   - A goal is a shared pot with a deadline. Bundling and quantity discounts
     describe one student's individual purchase, so they have no meaning
     against it — a goal is its own category with its own rules.

2. **Collective Goal Completeness**
   - If `collective_goal_type` is set, both `collective_goal_target` and `collective_goal_expires_at` MUST be set
   - If only some collective_goal fields are set, validation fails

### C. Value Range Rules

1. **Price:** Must be ≥ 0 (Decimal with 2 scale)
2. **economic_role:** MUST be exactly one of `necessity`, `convenience`, `add_on`. A value outside the enum is a validation failure; a price outside the role's reference band is not — pricing position is reported by the Helper, never enforced here.
3. **item_type:** MUST be exactly one of `immediate`, `delayed`, `hall_pass`, `privilege`, `collective`
4. **inventory_total:** If set, must be > 0
5. **auto_expiry_days:** If set, must be > 0
6. **bundle_quantity:** If set, must be > 1
7. **bulk_discount_quantity:** If set, must be > 1
8. **bulk_discount_percentage:** If set, must be in range [0, 100]
9. **Bulk discounts:** If either bulk-discount field is set, `entitlement_type` MUST be `IMMEDIATE_USE`, `DELAYED_USE`, or `HALL_PASS`. Privilege and collective-goal products cannot use bulk discounts.
10. **collective_goal_target:** If set, must be > 0
11. **collective_goal_expires_at:** If set, must be a valid future datetime

### D. Teacher-facing creation sequence and gates

Blank optional inputs resolve as follows: `holding_limit`,
`inventory_total`, `auto_expiry_days`, `redemption_prompt`, and
`auto_delist_date` remain unlimited, perpetual, empty, or unset as applicable;
boolean options default to `false`, except the mandatory direct-purchase
behavior for non-rent-linked products, which defaults to `true`.

Sellability is not a payload boolean. It is the `availability_state`
projection (`IN_USE`, `HIDDEN`, `RETIRED`) owned by `DOM-POL-001` §IX, and it
is the only part of a persisted version that may change.

The creation form follows this order because each decision narrows the legal
configuration surface that follows it:

```text
REQUIRED: item type
        |
        v
ITEM TYPE GATE
  immediate  -> no redemption prompt, expiry, bundle, or goal; bulk discount allowed
  delayed    -> redemption prompt and expiry become available
  hall_pass  -> delayed-style holding settings; grant lifecycle applies
  privilege  -> holding limit hard-set to 1; no bundle or goal
  collective -> goal settings become available; bundle/bulk settings disappear
        |
        v
RENT LINK GATE
  not rent-linked -> direct purchase is mandatory; no direct-purchase toggle
  rent-linked     -> show direct-purchase toggle and rent quantity
                    -> rent grant quantity is required and positive
        |
        v
ECONOMIC ROLE
  required for every product -> drives the Helper projection only;
                                grants no purchase authorization
        |
        v
ACQUISITION / HOLDING
  inventory blank       -> unlimited inventory
  holding limit blank   -> unlimited active holdings
        |
        v
LIFECYCLE / ADVANCED
  activation blank      -> sellable as soon as the version is IN_USE
  auto-expiry blank     -> no Store expiry for applicable types
  redemption blank      -> no redemption prompt
  auto-delist blank     -> no automatic delisting date
  boolean options blank -> their documented false default applies
```

The UI MAY hide fields before this sequence reaches them, but the server MUST
reapply every gate and reject an otherwise hidden illegal field combination.

## VI. Example Payloads

### Example 1: Simple Delayed-Use Hall Pass

```json
{
  "product_id": 101,
  "is_purchasable": true,
  "supports_direct_grants": true,
  "price": "50.00",
  "entitlement_type": "DELAYED_USE",
  "name": "Hall Pass - Bathroom",
  "description": "Valid for 30 days",
  "auto_expiry_days": 30,
  "economic_role": "necessity"
}
```

### Example 1A: Hall Pass

```json
{
  "product_id": 101,
  "is_purchasable": true,
  "supports_direct_grants": true,
  "price": "50.00",
  "entitlement_type": "HALL_PASS",
  "name": "Hall Pass - Bathroom",
  "description": "Valid for 30 days",
  "auto_expiry_days": 30,
  "economic_role": "necessity"
}
```

### Example 2: Immediate-Use Privilege

```json
{
  "product_id": 102,
  "is_purchasable": true,
  "supports_direct_grants": true,
  "price": "75.00",
  "entitlement_type": "PRIVILEGE",
  "name": "Seat Selection",
  "description": "Choose your own seat for one term",
  "economic_role": "convenience"
}
```

### Example 3: Collective Goal Product

```json
{
  "product_id": 103,
  "is_purchasable": true,
  "supports_direct_grants": false,
  "price": "25.00",
  "entitlement_type": "COLLECTIVE_GOAL",
  "name": "Class Pizza Party",
  "collective_goal_type": "fixed",
  "collective_goal_target": 50,
  "collective_goal_expires_at": "2026-08-31T23:59:59Z",
  "description": "50 purchases triggers class pizza party",
  "economic_role": "add_on"
}
```

### Example 4: Bulk Discount Product

```json
{
  "product_id": 104,
  "is_purchasable": true,
  "supports_direct_grants": false,
  "price": "10.00",
  "entitlement_type": "DELAYED_USE",
  "name": "Homework Pass",
  "auto_expiry_days": 60,
  "bulk_discount_quantity": 5,
  "bulk_discount_percentage": 15.0,
  "description": "Buy 5+ for 15% discount",
  "economic_role": "necessity"
}
```

## VII. Parser Contract

### Input

A JSON object (dict) from `policy_version.payload`

### Parsing Rules (Mandatory)

1. **Enumerate all payload keys.** Before processing any field, collect the set of all keys in the input.
2. **Reject unknown fields.** If any key is not declared in Section IV (Required or Optional fields), raise `ValueError` immediately with message: `"Unknown field in payload: {key}"`. **This is fail-fast; do not continue processing.**
3. **Process declared fields only.** Extract only the declared fields listed in Section IV.A (Required) and Section IV.C (Optional).
4. **Validate required fields.** Each required field MUST be present and non-null.
5. **Validate optional fields.** Optional fields MAY be null or missing; if present and non-null, apply type and range validation per Section V.
6. **Validate combinations.** Apply all mutual-exclusion and type-specific rules from Section V.

### Output

A typed `StoreProductConfig` object with all required fields set and optional fields set or defaulted.

If any validation step fails, raise an exception immediately. Do not attempt recovery or partial parsing.

### Exceptions

| Condition | Exception Type | Message |
|-----------|----------------|---------|
| Unknown field in payload | `ValueError` | "Unknown field in payload: {key}" |
| Required field missing | `ValueError` | "Required field {name} missing" |
| Invalid entitlement_type | `ValueError` | "Invalid entitlement_type: {value}" |
| Invalid combination | `ValueError` | "Invalid combination: {reason}" |
| Price negative | `ValueError` | "Price cannot be negative" |
| Type mismatch | `TypeError` | "Field {name} must be {type}, got {actual_type}" |

**All exceptions are fatal and prevent payload acceptance.**

## VIII. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-07-28 | Initial specification |
| 1.1 | 2026-09-13 | Retired the Store pricing tier. Added required `economic_role` (`necessity`, `convenience`, `add_on`) per SPEC-ECON-003 §4.7 |
| 1.2 | 2026-09-13 | Declared the persisted fields Section V.D already depended on (`item_type`, `inventory_total`, `activation_at`, `auto_delist_date`, `redemption_prompt`), closing a Section III.A governance gap. Added Section IV.D distinguishing persisted inputs from derived projections and fixing `economic_role` as advisory per DOM-STORE-001 §XII. Replaced the stale `is_active` reference with the `availability_state` projection. Added `economic_role` to Examples 2-4 and corrected malformed JSON in Example 2. Renumbered Section V.C and restored A/B/C/D section order |

## IX. Amendment Process

Any change to this specification (add, remove, rename, or change semantics/type of a field) MUST follow this process:

1. **Update this document**
   - Increment version number
   - Update effective date
   - Document change in Version History section
   - Document rationale for change

2. **Audit all consuming code**
   - Identify all parsers and validators that consume STORE_PRODUCT payloads
   - Identify all callers that persist STORE_PRODUCT payloads
   - Ensure all code is updated before the new effective date

3. **Update parser/validator implementations**
   - Required: Enforce the new schema (added/removed/changed fields)
   - Required: Reject payloads that don't match the new schema
   - Add migration logic if existing policies must be upgraded

4. **Migration guidance (if applicable)**
   - If this change affects existing policies in production, add a section documenting:
     - Which existing policies are affected
     - How to migrate them (automated or manual)
     - Effective date for migration
     - Rollback procedure if needed

5. **Update related documents**
   - Update DOM-STORE-001 if semantic authority changes
   - Update FEAT-STOR-001 and FEAT-STOR-004 if behavior changes
   - Update any other SPEC documents that reference this one (e.g., SPEC-OBL-001 for insurance payloads)

6. **No retroactive weakening**
   - Once a version is effective, a future version MUST NOT silently accept old payloads without migration
   - Parsers must reject unknown fields, always

## X. Implementation Guidance

### For Payload Creators (Policies domain)

- Never persist undeclared fields, even if "it might be useful later"
- When a new field is needed, follow the Amendment Process
- Use the SPEC as the contract: if it's not in the SPEC, it cannot be in the payload

### For Payload Consumers (FEAT-STOR-001, FEAT-STOR-004, etc.)

- Parse payloads using `StoreProductConfig.from_payload(payload)`
- Never attempt to infer or assume fields beyond what the parser provides
- Never attempt to access undeclared fields
- Treat parser exceptions as fatal (do not recover)

### For Future SPEC Amendments

- Document the rationale for every change
- Consider backward compatibility implications
- Update this entire document, not just the changed section
- Increment the version number
