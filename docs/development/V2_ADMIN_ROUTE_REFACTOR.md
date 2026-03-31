

# V2 Admin Route Refactor Plan

**Status:** Active (Post-Port Structural Refactor)
**Scope:** `app/routes/admin.py`

---

## I. Purpose

This document defines the structural refactor plan for the `admin.py` route layer.

The goal is to transition from a monolithic route file containing mixed concerns
into a clean separation of:

- Routes (HTTP interface only)
- Services (business logic)
- Models (data layer)

This refactor does NOT change system behavior. It is purely structural.

---

## II. Current State

`admin.py` currently contains:

- Route handlers
- Business logic
- Multi-table database operations
- Destructive workflows (deletion)
- Scope resolution (join_code / class_id)
- Analytics and economy calculations
- Payroll and attendance aggregation

This results in:

- High cognitive load
- Difficult debugging
- Increased risk for destructive operations
- Tight coupling between HTTP and domain logic

---

## III. Target State

### Architecture

```
routes/   → HTTP interface (thin)
services/ → business logic (heavy)
models/   → data definitions
```

### Route Responsibilities

Routes MUST:

- parse request input
- call appropriate service functions
- return responses

Routes MUST NOT:

- perform multi-table DB logic
- contain business rules
- implement destructive workflows
- compute analytics or financial logic

---

## IV. Extraction Plan

Refactoring will be performed incrementally by domain.

---

### 1. Deletion Service (Highest Priority)

**Target:** `services/deletion_service.py`

Move:

- `_hard_delete_join_code_scope`
- `_hard_delete_teacher_account_scope`
- `_delete_*`
- `_assert_transaction_deletion_allowed`

Rationale:

- These represent system invariants
- High risk operations must be isolated

---

### 2. Economy Service

**Target:** `services/economy_service.py`

Move:

- `_build_economy_snapshot_from_analysis`
- `_get_frozen_economy_analysis_payload`
- `_build_policy_summary`
- `_build_rebalance_preview`
- `_build_insurance_recommendation_context`
- `_load_economy_rebalance_context`
- `_apply_rebalance_plan`

Rationale:

- Complex computation logic
- Cross-cutting domain behavior

---

### 3. Payroll Service

**Target:** `services/payroll_service.py`

Move:

- `_build_payroll_preview_state`
- `_resolve_payroll_settings_for_block`
- `auto_tapout_all_over_limit`

Rationale:

- Aggregation-heavy logic
- Independent domain concern

---

### 4. Scope Service (Critical for v2)

**Target:** `services/scope_service.py`

Move:

- `_resolve_class_id`
- `_resolve_join_code_for_block`
- `require_admin_feature_scope`
- `get_admin_feature_settings_for_join_code`
- `is_admin_feature_enabled`

Rationale:

- Centralizes class scoping logic
- Prepares for strict `class_id` enforcement

---

### 5. Roster Service

**Target:** `services/roster_service.py`

Move:

- `_link_student_to_admin`
- `_ensure_teacher_student_seat`

---

## V. Post-Refactor Route Pattern

### Before

```
@admin_bp.route('/example')
def example():
    # large block of logic
    scope = require_admin_feature_scope(...)
    data = _build_economy_snapshot_from_analysis(...)
    db.session.commit()
```

### After

```
@admin_bp.route('/example')
def example():
    scope = scope_service.resolve_scope_from_request(...)
    data = economy_service.get_snapshot(scope)
    return jsonify(data)
```

---

## VI. Naming Conventions

Service functions MUST follow consistent naming:

- `resolve_*` → identity/scope
- `get_*` → read-only
- `build_*` → computed structures
- `apply_*` → state changes
- `delete_*` → destructive operations

---

## VII. Guardrails

- No new business logic may be added to `admin.py`
- All new domain logic MUST be implemented in services
- Routes exceeding ~50–100 lines SHOULD be refactored

---

## VIII. Migration Strategy

Refactor will be performed incrementally:

1. Extract deletion service
2. Extract economy service
3. Extract scope service
4. Extract remaining domains

Each step must:

- preserve behavior
- pass all tests
- avoid schema changes

---

## IX. Outcome

After completion:

- `admin.py` becomes a thin orchestration layer
- business logic is modular and testable
- system invariants are isolated
- future architecture enforcement (class_id-only) becomes straightforward

---

## X. Notes

This refactor aligns with:

- V2_Class_Scope_Normalization_Target
- CI enforcement of join_code boundary

It is a prerequisite for strict enforcement of class-scoped invariants.