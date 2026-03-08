# LOG-ARC-043: Documentation vs. Code Cross-Reference Audit

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| LOG-ARC-043      | 1.0     | 2026-03-08     | N/A        | Informative     |

**Date:** 2026-03-08
**Reviewer:** Claude Code
**Branch:** codex/v2.0
**Scope:** Complete cross-reference of all documentation files against actual runtime implementation in `app/`

---

## Overview

This audit systematically validates every documentation claim against the real codebase. Each finding is classified into one of three categories:

- **Cat-1 (Doc-Not-App):** Documented behavior or structure that does not exist in the current codebase.
- **Cat-2 (App-Not-Doc):** Working code with no corresponding documentation.
- **Cat-3 (Irreconcilable):** Documentation and code describe two realities that cannot both be true; any developer or AI agent following the documentation would produce incorrect behavior at runtime.

---

## Cat-1: Documented But Does Not Exist in App

### 1.1 — `students.teacher_id` presented as "deprecated but present"

**Source:** `.claude/rules/multi-tenancy.md`, section "Legacy `teacher_id` Column"

> "The `students.teacher_id` column is DEPRECATED and should not be used. Kept for backward compatibility during migration. ⏳ Future: Remove `teacher_id` column entirely."

**Reality:** The `Student` model (`app/models.py`, lines 341–440) has no `teacher_id` column. The migration plan marked ⏳ is already complete. The documentation presents a finished migration as a pending future task.

---

### 1.2 — `TeacherBlock.dob_sum` compatibility alias

**Source:** `ARC-OPS-007`, Section VI

> "`TeacherBlock.dob_sum` compatibility alias for `dob_sum_hash`"

**Reality:** `TeacherBlock` (`app/models.py`, lines 249–340) has only a `dob_sum_hash` column. No `dob_sum` synonym, alias, or property exists anywhere on the model.

---

### 1.3 — `StudentBlock` fields: `is_active`, `checking_balance`, `savings_balance`

**Source:** `.claude/rules/multi-tenancy.md`, "Core Tables" schema diagram and "Pattern 3: Get Student Balance"

Documented schema:
```
StudentBlock
├── checking_balance
├── savings_balance
└── is_active
```

Documented code pattern:
```python
return {
    'checking': student_block.checking_balance,
    'savings': student_block.savings_balance
}
```

**Reality:** `StudentBlock` (`app/models.py`, lines 1076–1112) contains only: `id`, `student_id`, `seat_id`, `period`, `join_code`, `tap_enabled`, `done_for_day_date`, `rent_hall_passes`, `created_at`, `updated_at`. None of the three documented fields exist. Balances are computed properties on `Student` via `Transaction` aggregation, not stored in `StudentBlock`. Accessing these attributes at runtime raises `AttributeError`.

---

### 1.4 — Blueprint structure: `routes/auth.py` and three missing files

**Source:** `.claude/CLAUDE.md`, Architecture Patterns section

Documented routes directory:
```
routes/
├── admin.py
├── student.py
├── system_admin.py
├── api.py
└── auth.py          ← listed
```

**Reality:** `app/routes/` contains eight files: `admin.py`, `analytics.py`, `api.py`, `docs.py`, `main.py`, `recovery.py`, `student.py`, `system_admin.py`. There is no `auth.py` in routes — the auth module lives at `app/auth.py`. Three entire blueprints (`analytics`, `main`, `recovery`) are absent from the listed structure.

---

### 1.5 — Model count: "41 SQLAlchemy models"

**Source:** `.claude/CLAUDE.md`

> "41 SQLAlchemy models including..."

**Reality:** `app/models.py` (2,936 lines) contains 55+ class definitions. Models not listed anywhere in CLAUDE.md include: `AnalyticsAlert`, `JoinCode`, `User`, `IdentityProfile`, `Seat`, `ClassEconomy`, `ClassMembership`, `BalanceCache`, `PayrollCache`, `RentItem`, `RedemptionAuditLog`, `AnalyticsSnapshot`, `AnalyticsEvent`, `Issue`, `IssueCategory`, `TicketCorrelationPack`, `IssueStatusHistory`, `IssueResolutionAction`, `ActorRequestTrace`, `ErrorEvent`, `ErrorLog`, `AdminInviteCode`, `TeacherOnboarding`, `AdminCredential`, `SystemAdminCredential`, `FeatureSettings`, `UserReport`.

---

### 1.6 — `summons` as a default hall pass type

**Source:** `FEAT-HALL-001`, Section VIII

> "For reasons other than `office`, `summons`, `done for the day`, student must have pass balance."

**Reality:** `HallPassSettings.get_default_pass_types()` (`app/models.py`, lines 1223–1232) returns only: Bathroom, Water Fountain, Office, Nurse, Counselor. No `Summons` pass type exists in the codebase. Additionally, `done for the day` is a student state on `StudentBlock`, not a hall pass reason type; mixing these categories in the same sentence is misleading.

---

### 1.7 — Sysadmin capabilities omitted from `ARC-SYS-001`

**Source:** `ARC-SYS-001`, Section VI, which claims to document "implemented capabilities."

**Reality:** The following active routes in `system_admin.py` are not mentioned:

| Route | Line | Purpose |
|-------|------|---------|
| `/admins` | 837 | Admin listing |
| `/admins/<int:admin_id>/reset-totp` | 869 | TOTP reset |
| `/admins/<int:admin_id>/delete` | 914 | Admin deletion |
| `/delete-period/<int:admin_id>/<string:period>` | 1211 | Period deletion |
| `/manage-teachers/void/<int:code_id>` | 1099 | Invite code void |
| `/manage-teachers/delete/<int:admin_id>` | 1218 | Teacher deletion |
| `/logs-testing` | 715 | Log testing route |

---

## Cat-2: Exists in App But Not Documented

### 2.1 — `recovery.py` blueprint (entire)

Routes: `/recovery/admin/generate-code/<student_id>`, `/recovery/`, `/recovery/lookup`, `/recovery/verify-identity`

No mention in CLAUDE.md blueprint structure, no architecture document covers this blueprint. This is a separate credential-recovery entrypoint for students, distinct from teacher recovery in `admin.py`.

---

### 2.2 — `main.py` blueprint (entire)

Routes: `/`, `/health`, `/health/deep`, `/privacy`, `/terms`, `/offline`, `/sw.js`, `/hall-pass/terminal`, `/hall-pass/queue`, `/verify/hallpass/<teacher_public_token>`, `/debug/filters`, `/switch-view`, `/debug/admin-db-test`

Not listed in CLAUDE.md blueprint structure. This blueprint contains the sole implementation of the public hall-pass verification flow (`/verify/hallpass/`), making this a significant architectural omission.

---

### 2.3 — `analytics.py` blueprint route surface

`FEAT-MET-001` specifies analytics design principles but documents no actual route URLs. Implemented routes:

- `/analytics/` — dashboard
- `/analytics/api/snapshot/<window_type>`
- `/analytics/api/alerts`
- `/analytics/alert/<int:alert_id>/acknowledge`
- `/analytics/events`
- `/analytics/student/<int:student_id>`

---

### 2.4 — `docs.py` blueprint

A routes file exists in `app/routes/docs.py` with no documentation of purpose, routes, or content anywhere in the project.

---

### 2.5 — `app/services/` and `app/utils/` directories

`app/services/`: `balance_service.py`, `tlcp.py`

`app/utils/` (25+ modules): `analytics_engine.py`, `banking.py`, `claim_credentials.py`, `constants.py`, `deletion.py`, `economy_balance.py`, `insurance_eligibility.py`, `money_guard.py`, `overdraft.py`, `passwordless_client.py`, `seat_scope.py`, `student_deletion.py`, `turnstile.py`, `username_migration.py`, and others.

None of these are mentioned in CLAUDE.md "Key Files" or any architecture document. `analytics_engine.py` is the runtime backend driving the entire analytics feature spec in `FEAT-MET-001`.

---

### 2.6 — Critical v2 models not in `ARC-OPS-007`

`ARC-OPS-007` documents v2 class boundaries and key tables but omits the following models that are active in production:

| Model | Significance |
|-------|-------------|
| `AnalyticsAlert` | Alert lifecycle with uniqueness constraints per window/class |
| `AnalyticsSnapshot` / `AnalyticsEvent` | Analytics data storage backing FEAT-MET-001 |
| `BalanceCache` | Core to ledger settlement — balance reads use this table |
| `PayrollCache` | Cached payroll breakdown by teacher |
| `RedemptionAuditLog` | Audit trail for store redemption approvals/rejections |
| `JoinCode` | UUID-keyed join code registry used for cascade deletes |
| `User` / `IdentityProfile` / `Seat` | v2 identity and seating infrastructure |
| `AdminInviteCode` | Teacher signup invite mechanism |
| `TeacherOnboarding` | Teacher onboarding state tracking |
| `FeatureSettings` | Per-class feature toggle model |
| `Issue`, `IssueCategory`, `TicketCorrelationPack`, `IssueStatusHistory`, `IssueResolutionAction` | Full ticket system |
| `ErrorLog`, `ErrorEvent`, `ActorRequestTrace` | Observability infrastructure |
| `UserReport` | Abuse/bug/feedback reports |

---

### 2.7 — Admin routes with no documentation

The following `admin.py` routes are not listed in `ARC-OPS-005` or any feature document:

- `/admin/economy-health` (line 6650)
- `/admin/feature-settings` (line 9450)
- `/admin/bonuses` (line 1524)
- `/admin/backfill-transactions` (line 1640)

---

### 2.8 — `scheduled_tasks.py` module

`app/scheduled_tasks.py` exists but is not mentioned in any architecture document or CLAUDE.md.

---

### 2.9 — `Announcement` model: teacher-authorship

`ARC-SYS-001` covers announcements exclusively as a sysadmin capability. The `Announcement` model (`app/models.py`, line 2670) has both `teacher_id` and `system_admin_id` foreign keys, allowing teachers to author announcements as well. This is not documented.

---

## Cat-3: Irreconcilable Conflicts

### 3.1 — `.claude/rules/multi-tenancy.md`: `StudentBlock` as class isolation authority

**What the doc says:**

The entire multi-tenancy rules file treats `StudentBlock` as the join table for class isolation, labeling this pattern as `✅ CORRECT`:

```python
students = Student.query.join(StudentBlock).filter(
    StudentBlock.join_code == join_code,
    StudentBlock.is_active == True   # field does not exist
).all()
```

The schema diagram shows `StudentBlock.join_code` as "FK to TeacherBlock.join_code — CRITICAL FOR SCOPING."

**What the app does:**

- `StudentBlock` has no `is_active` field, no balance columns, and `join_code` is a plain nullable indexed column with no FK constraint.
- In v2, `ClassMembership` is the class boundary authority, per `ARC-OPS-007`.
- `StudentBlock` is a per-student settings/state record (`tap_enabled`, `done_for_day_date`, `rent_hall_passes`), not a membership or access-control table.

**Consequence:** Every code example labeled `✅ CORRECT` in `.claude/rules/multi-tenancy.md` would raise `AttributeError` at runtime or produce incorrect results. The v1 query patterns no longer map to the v2 data model. Any AI agent or developer following these rules as authoritative would write broken code.

---

### 3.2 — `ARC-OPS-005`: `/admin/issues` route

**What the doc says:**

> "`/admin/issues` — current issue queue respects selected authorized class"

**What the app does:**

No `/admin/issues` route exists in `admin.py`. Teacher issues are handled at `/admin/help-support` (`admin.py`, line 9260). The `/issues` path exists only in the sysadmin namespace (`system_admin.py`, line 1852), behind a different role and different access control. The documented endpoint name, role namespace, and access context are all simultaneously wrong.

---

### 3.3 — `students.teacher_id`: "deprecated but exists" vs already removed

**What the doc says** (`.claude/rules/multi-tenancy.md`):

> "Current Status: The `students.teacher_id` column is DEPRECATED... Kept for backward compatibility during migration. ⏳ Future: Remove `teacher_id` column entirely."

This language presents the column as currently present.

**What the app does:**

The `Student` model (lines 341–440) has no `teacher_id` column. The migration plan is complete. The documentation presents a finished migration as pending.

> Note: This finding also appears in Cat-1 (1.1), but is listed here because the conflict is stronger than a simple omission — the documentation actively asserts a current state that is false.

---

### 3.4 — `FEAT-HALL-001`: `done for the day` as a hall pass lifecycle state

**What the doc says** (`FEAT-HALL-001`, Section VI):

> "Lifecycle state: `left` → `done for the day` (student forgot to checkin and time elapsed)"

**What the app does:**

`HallPassLog.status` (`app/models.py`, line 1180) accepts: `pending`, `approved`, `rejected`, `left`, `returned`. There is no `done for the day` status in the `hall_pass_logs` table. `done_for_day_date` is a separate field on `StudentBlock` that tracks a different behavioral lock. The document conflates two unrelated systems into one lifecycle state.

---

### 3.5 — `.claude/CLAUDE.md`: Student model described as pre-v2 skeleton

**What the doc says:**

CLAUDE.md implies the `Student` model is a lightweight record with basic fields: `first_name`, `last_initial`, deprecated `teacher_id`, and basic credentials.

**What the app has:**

The `Student` model includes `identity_id` (FK to `IdentityProfile`), `block`, `join_code`, `join_code_id`, `salt`, `first_half_hash`, `second_half_hash`, `username_hash`, `username_lookup_hash`, `is_teacher`, `money_action_cooldown_until`, `opaque_reference`, `internal_reference`, `has_completed_profile_migration`, `second_factor_type`, `second_factor_enabled`, and recovery fields. The model described in CLAUDE.md is the pre-v2 structure; the actual model is substantially different in column count, identity architecture, and credential layout.

---

## Summary Table

| ID | Source | Finding | Category |
|----|--------|---------|----------|
| 1.1 | `multi-tenancy.md` | `students.teacher_id` described as deprecated-but-existing; already removed | Cat-1 |
| 1.2 | `ARC-OPS-007` | `TeacherBlock.dob_sum` alias claimed; does not exist | Cat-1 |
| 1.3 | `multi-tenancy.md` | `StudentBlock.is_active`, `.checking_balance`, `.savings_balance` documented; none exist | Cat-1 |
| 1.4 | `CLAUDE.md` | `routes/auth.py` listed; `analytics.py`, `main.py`, `recovery.py` missing | Cat-1 |
| 1.5 | `CLAUDE.md` | "41 models" claimed; actual count is 55+ | Cat-1 |
| 1.6 | `FEAT-HALL-001` | `summons` pass type and `done for the day` in pass-balance rule; neither is a default pass type | Cat-1 |
| 1.7 | `ARC-SYS-001` | Seven implemented sysadmin routes not listed | Cat-1 |
| 2.1 | — | `recovery.py` blueprint: undocumented | Cat-2 |
| 2.2 | — | `main.py` blueprint (incl. hall-pass verification route): undocumented | Cat-2 |
| 2.3 | — | `analytics.py` route URLs: undocumented | Cat-2 |
| 2.4 | — | `docs.py` blueprint: undocumented | Cat-2 |
| 2.5 | — | `app/services/` and `app/utils/` (25+ modules): undocumented | Cat-2 |
| 2.6 | `ARC-OPS-007` | 14+ active models absent from schema doc | Cat-2 |
| 2.7 | `ARC-OPS-005` | Four admin routes absent from API reference | Cat-2 |
| 2.8 | — | `scheduled_tasks.py`: undocumented | Cat-2 |
| 2.9 | `ARC-SYS-001` | Teacher-authored announcements: undocumented | Cat-2 |
| **3.1** | **`multi-tenancy.md`** | **All "CORRECT" patterns use v1 `StudentBlock` fields that do not exist; would fail at runtime** | **Cat-3** |
| **3.2** | **`ARC-OPS-005`** | **`/admin/issues` does not exist; teacher route is `/admin/help-support`** | **Cat-3** |
| **3.3** | **`multi-tenancy.md`** | **`teacher_id` described as "exists but deprecated"; column already removed** | **Cat-3** |
| **3.4** | **`FEAT-HALL-001`** | **`done for the day` listed as `HallPassLog.status` value; not in model** | **Cat-3** |
| **3.5** | **`CLAUDE.md`** | **Student model described as pre-v2 skeleton; actual model is structurally different** | **Cat-3** |

---

## Recommended Remediation by Priority

### Priority 1 — Critical (Cat-3: will produce broken behavior)

1. **Rewrite `.claude/rules/multi-tenancy.md` query examples** to use `ClassMembership` as the v2 class boundary. Remove or correct all code blocks referencing `StudentBlock.is_active`, `StudentBlock.checking_balance`, `StudentBlock.savings_balance`. Remove the `students.teacher_id` "deprecated" section — the column is gone.
2. **Fix `ARC-OPS-005` `/admin/issues`** → correct to `/admin/help-support` (teacher context) or clearly scope it to sysadmin.
3. **Fix `FEAT-HALL-001` Section VI** — remove `done for the day` from the `HallPassLog` status lifecycle. Document it as a `StudentBlock` behavioral state, separate from the hall pass state machine.
4. **Update `.claude/CLAUDE.md` Student model description** to reflect the v2 column set.

### Priority 2 — High (Cat-2: undocumented working code)

5. **Document `recovery.py` and `main.py`** in CLAUDE.md blueprint structure.
6. **Add `BalanceCache` to `ARC-OPS-007`** — it is central to the ledger settlement model and balance read paths.
7. **Document `app/utils/analytics_engine.py`** as the runtime backend for `FEAT-MET-001`.
8. **Expand `ARC-SYS-001`** to include the admin management, TOTP reset, period deletion, and teacher deletion routes.

### Priority 3 — Medium (Cat-1: stale claims)

9. **Remove `TeacherBlock.dob_sum` alias claim** from `ARC-OPS-007`.
10. **Update CLAUDE.md model count and blueprint list** to match current state.
11. **Clarify `summons` in `FEAT-HALL-001`** — either add it as a supported pass type or remove the reference.

---

## Amendment

This is an informative log. It does not define rules. Corrections to the findings above should be applied to the source documents identified in each finding, not to this report.
