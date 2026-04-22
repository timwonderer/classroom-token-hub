# Temporal Invariant Audit

| Field | Value |
|-------|-------|
| Audit Date | 2026-04-21 |
| Last Reviewed | 2026-04-22 |
| Specification | INV-ARC-015 v1.0 |
| Authority | `docs/development/v2_restructure_doc/INV-INVARIANT/ARCHITECTURE/INV-ARC-015_Temporal_Model_and_Boundary_Enforcement.md` |
| Status | **Individual violations remediated** — bad patterns removed; target `TemporalContext` architecture (per `V2_Temporal_Architecture_Rebuild_Plan.md`) is NOT yet implemented |

---

## What Is Done vs. What Remains

### ✅ Violation Remediation (done)

All V-001 through V-009 violations have been fixed at the call-site level:
- Hardcoded `America/Los_Angeles` removed from 11 of 12 sites
- `claim_period_bounds_utc()`, `local_date_bounds_utc()`, `week_bounds_utc()`, `month_bounds_utc()`, `semester_bounds_utc()` extracted to `app/utils/time.py`
- Routes import and use the centralized helpers
- `done_for_day_date` write sites use class-scoped timezone via `get_timezone()`
- Jinja2 filter delegates to `get_timezone()`

### ❌ Target Architecture (not implemented)

The `V2_Temporal_Architecture_Rebuild_Plan.md` defines an execution-model rebuild that has NOT been built:

| Target | Current State |
|--------|---------------|
| `TemporalContext` object, constructed once per request | Not implemented — no such class exists |
| Timezone sourced from `ClassConfig.get_timezone(class_id)` (class record) | Not done — `get_timezone()` still reads `session.get("timezone")` with Pacific fallback |
| `build_temporal_context(class_id, timestamp_utc)` public interface | Not implemented |
| All domains receive TemporalContext — routes MUST NOT compute time inline | Not done — routes still call `get_timezone()` at individual call sites |
| CI gates block `datetime.now`, `datetime.utcnow`, hardcoded timezones | Not implemented |
| Class timezone immutable and class_id-authoritative at runtime | DB column exists (`ClassEconomy.class_timezone`), but `get_timezone()` does not read it — session-driven |

**This distinction matters:** the violation fixes prevent correctness bugs today, but the target architecture is a larger structural project requiring dedicated implementation work. See `V2_Temporal_Architecture_Rebuild_Plan.md` for the full spec.

---

## Approved Temporal Layer

`app/utils/time.py` is the canonical time authority. It provides:

- `utc_now()` — single approved source of current time
- `get_timezone(tz_name?)` — resolves class IANA timezone from session, app config, or Pacific fallback
- `local_date_bounds_utc(local_day, tz_name?)` — converts a class-timezone calendar day into a UTC `[start, end)` range
- `local_date_end_utc(local_day, tz_name?)` — end of a class-timezone day in UTC
- `ensure_utc(dt)` — normalizes arbitrary datetime to UTC-aware
- `normalize_for_db(dt)` — strips tzinfo for SQLite comparisons

No `TemporalContext` class exists. These functions collectively serve that role.

---

## Invariants Under Audit (from INV-ARC-015)

| # | Rule |
|---|------|
| 1 | Time MUST only be sourced from the single canonical approved layer |
| 2 | No direct calls to system time (`datetime.now`, `datetime.utcnow`, `date.today`, `time.time`) outside approved layer |
| 3 | All timestamps MUST be UTC |
| 4 | No domain may compute or reinterpret time independently |
| 5 | No logic may span across the class-day boundary (`[00:00, 24:00)` in class timezone) |
| 6 | No timezone conversion outside centralized logic |
| 7 | No persistence of derived (non-UTC) time |

---

## Violation Register

---

### ✅ V-001 — UTC date used as class-day boundary in attendance

**Status: RESOLVED (2026-04-22)**

**File:** `app/attendance.py` — no longer uses `func.date()` or `utc_now().date()` for day comparisons. Attendance service now uses `local_date_bounds_utc()` from `app/utils/time.py` for UTC-range queries and `get_timezone()` for class-scoped resolution.

**Type:** Wrong temporal domain for day boundary  
**Classification:** ~~Must refactor~~ → Done

---

### ✅ V-002 — UTC midnight used as "start of today" for transaction count

**Status: RESOLVED (2026-04-22)**

**File:** `app/routes/admin.py` — `utc_now().replace(hour=0, ...)` pattern has been removed. Admin route now imports and uses `local_date_bounds_utc()` from `app/utils/time.py` for day-boundary queries.

**Type:** Day boundary anchored to UTC, not class timezone  
**Classification:** ~~Must refactor~~ → Done

---

### ✅ V-003 — `_get_period_bounds()` computes insurance claim windows in UTC (student route)

**Status: RESOLVED (2026-04-22)**

`claim_period_bounds_utc(period_key, tz_name)` has been extracted into `app/utils/time.py`. `app/routes/student.py` imports and calls it directly. The local `_get_period_bounds()` helper has been removed.

**Type:** Period boundaries computed in wrong temporal domain  
**Classification:** ~~Must refactor~~ → Done

---

### ✅ V-004 — `_get_period_bounds()` duplicated in admin route (identical violation)

**Status: RESOLVED (2026-04-22)**

`app/routes/admin.py` now imports and calls `claim_period_bounds_utc()` from `app/utils/time.py`. Local `_get_period_bounds()` removed.

**Type:** Period boundaries computed in wrong temporal domain  
**Classification:** ~~Must refactor~~ → Done

---

### ✅ V-005 — Hardcoded `America/Los_Angeles` across 12 call sites

**Status: LARGELY RESOLVED (2026-04-22)**

All 11 of 12 hardcoded `America/Los_Angeles` sites have been replaced with `get_timezone()` from `app/utils/time.py`. Module-level `PACIFIC` constants in `admin.py` and `analytics.py` have been removed. `app/routes/api.py`, `app/attendance.py`, and `app/services/attendance_service.py` now call `get_timezone()` with class-scoped timezone names.

**Remaining:** One low-risk config-fallback in `admin.py:1823`:
```python
return pytz.timezone(current_app.config.get('ECONOMY_REFRESH_TIMEZONE', 'America/Los_Angeles'))
```
This is a background scheduler timezone (not a class-day boundary decision). The fallback is intentional and configurable via `ECONOMY_REFRESH_TIMEZONE`. Acceptable to leave unless the scheduler becomes class-scoped.

**Type:** Hardcoded timezone bypasses canonical `get_timezone()` — not class-scoped  
**Classification:** ~~Must refactor~~ → Done (1 intentional config fallback remains)

---

### ✅ V-006 — UTC date used as default for insurance claim incident form

**Status: RESOLVED (2026-04-22)**

`app/routes/student.py` now uses `get_timezone()` to convert `utc_now()` to class-local time before calling `.date()` for the form default.

**Type:** Derived (non-UTC) date presented from UTC source  
**Classification:** ~~Must refactor~~ → Done

---

### ✅ V-007 — Analytics week/month windows use UTC weekday

**Status: RESOLVED (2026-04-22)**

`app/routes/student.py` now converts to class-local time via `get_timezone()` before anchoring week/month boundaries. UTC-domain `.weekday()` and `.replace(day=1)` shortcuts have been removed.

**Type:** Analytics windows anchored to UTC domain  
**Classification:** ~~Must refactor~~ → Done

---

### ✅ V-008 — `done_for_day_date` persists a derived Pacific date

**Status: RESOLVED (2026-04-22)**

All write sites (`api.py`, `attendance.py`) now derive `today_local` via `get_timezone(tz_name)` (class-scoped) rather than `utc_now().astimezone(pacific)`. The column remains `db.Date` and is now correctly interpreted as the calendar date in the class's timezone.

**Type:** Persistence of derived, non-UTC, timezone-specific date  
**Classification:** ~~Must refactor~~ → Done

---

### ✅ V-009 — Jinja2 filter duplicates `get_timezone()` logic inline

**Status: RESOLVED (2026-04-22)**

`app/__init__.py` now imports and delegates to `get_timezone()` from `app/utils/time.py` for the Jinja2 template filter. The inline `pytz.timezone(session.get('timezone', 'America/Los_Angeles'))` pattern has been removed.

**Type:** Timezone resolution outside centralized logic  
**Classification:** ~~Must refactor~~ → Done

---

### 🟢 V-010 — `time.time()` for fallback code suffix generation

**Files:** `app/routes/admin.py:1490`, `:4133`, `:4567`, `:9372`
**Code:**
```python
timestamp_suffix = int(time.time()) % FALLBACK_CODE_MODULO
```

**Type:** Raw system time call
**Risk:** Low — harmless
**Invariants broken:** None meaningfully (entropy source for opaque code uniqueness, not a stored timestamp or boundary decision)

**Classification:** Safe to keep
**Note:** Could be replaced with `int(utc_now().timestamp())` for surface consistency, but carries no correctness risk as-is.

---

### 🟢 V-011 — `datetime.now()` in test file

**File:** `tests/test_decimal_precision.py:241`
**Code:**
```python
now = datetime.now()
```

**Type:** Naive system time in test
**Risk:** Low (test-only, no production impact)
**Invariants broken:** 2 (technically)

**Classification:** Safe to keep — replace with `utc_now()` during next test maintenance pass.

---

## Classification Summary

| ID | Location | Classification | Status |
|----|----------|---------------|--------|
| V-001 | `app/attendance.py:121,139` | Must refactor | ✅ Resolved |
| V-002 | `app/routes/admin.py:2495` | Must refactor | ✅ Resolved |
| V-003 | `app/routes/student.py:2028–2048` | Must refactor | ✅ Resolved |
| V-004 | `app/routes/admin.py:7403–7423` | Must refactor | ✅ Resolved |
| V-005 | 12 sites — hardcoded `America/Los_Angeles` | Must refactor | ✅ 11/12 resolved; 1 config fallback intentional |
| V-006 | `app/routes/student.py:2023` | Must refactor | ✅ Resolved |
| V-007 | `app/routes/student.py:1319–1320` | Must refactor | ✅ Resolved |
| V-008 | `app/models.py:1021` + 5 write sites | Must refactor | ✅ Resolved |
| V-009 | `app/__init__.py:70–97` | Must refactor | ✅ Resolved |
| V-010 | `app/routes/admin.py:1490,4133,4567,9372` | Safe to keep | ✅ No change needed |
| V-011 | `tests/test_decimal_precision.py:241` | Safe to keep | ✅ No change needed |

---

## System-Level Temporal Map

### Where Time Enters the System

| Entry Point | Correct? | Notes |
|-------------|----------|-------|
| `app/utils/time.py:utc_now()` | Yes | Canonical approved entry — all domains should use this |
| `pytz.timezone('America/Los_Angeles')` × 12 | No | Bypasses `get_timezone()`, not class-scoped (V-005) |
| `time.time()` × 4 in admin.py | Tolerated | Entropy for code generation only, not temporal logic (V-010) |
| `datetime.now()` in test | Minor | Test-only, no prod impact (V-011) |

### Where Time Is Transformed

| Location | Transform | Correct? |
|----------|-----------|----------|
| `time.py:get_timezone()` | Resolves class IANA tz from session/config | Yes |
| `time.py:local_date_bounds_utc()` | Local calendar day → UTC `[start, end)` range | Yes |
| `time.py:ensure_utc()` | Normalizes arbitrary datetime to UTC-aware | Yes |
| `main.py:286–291` | `utc_now()` → class tz → day bounds → UTC | Yes |
| `analytics.py:44–46` | `utc_now()` → Pacific → anchor → UTC | No — Pacific hardcoded (V-005) |
| `attendance.py:348–354` | `utc_now()` → Pacific day bounds → UTC | No — Pacific hardcoded (V-005) |
| `services/attendance_service.py:75–79` | Pacific → start/end UTC | No — Pacific hardcoded (V-005) |
| `student.py:2028–2048` `_get_period_bounds()` | `utc_now()` `.month` / `.weekday()` used raw | No — UTC domain, wrong (V-003) |
| `admin.py:7403–7423` `_get_period_bounds()` | Same | No — UTC domain, wrong (V-004) |
| `admin.py:2495` | `utc_now().replace(hour=0)` | No — UTC midnight as boundary (V-002) |
| `attendance.py:121` | `utc_now().date()` | No — UTC date, not class-tz date (V-001) |
| `__init__.py:70–97` | Session tz → display conversion inline | Partial — duplicates `get_timezone()` (V-009) |

### Where Time Is Used for Decisions

| Decision | Location | Correct? |
|----------|----------|----------|
| Is student done for the day? | `api.py:2029–2032` | Partial — depends on Pacific-hardcoded `today_pacific` (V-005) |
| Attendance "today" check | `attendance.py:121,139` | No — UTC date used (V-001) |
| Transactions today (dashboard) | `admin.py:2495` | No — UTC midnight boundary (V-002) |
| Insurance claim period limits | `student.py:2028`, `admin.py:7403` | No — UTC month/weekday (V-003, V-004) |
| Student weekly/monthly analytics | `student.py:1319–1320` | No — UTC weekday/month (V-007) |
| Analytics window anchor | `analytics.py:44–46` | No — Pacific hardcoded (V-005) |
| Rent/tax overdue check | `admin.py:4242–4251` | Partial — Pacific hardcoded (V-005) |
| Tap-in/out daily reset | `api.py:2229–2234` | Partial — Pacific hardcoded (V-005) |
| Insurance form date default | `student.py:2023` | No — UTC date (V-006) |
| Session timeout check | `auth.py:245` | Yes — `utc_now()` comparison |
| Recovery request expiry | `student.py:1313` | Yes — `utc_now()` comparison |

### Where Boundaries Are Enforced or Violated

| Boundary | Location | Status |
|----------|----------|--------|
| Day start/end → UTC range | `main.py:286–291` | Correct pattern |
| Day start/end → UTC range | `admin.py:9634–9640` | Pacific hardcoded, otherwise correct |
| Day start/end → UTC range | `api.py:2233–2236` | Pacific hardcoded, otherwise correct |
| Day start/end → UTC range | `attendance.py:348–354` | Pacific hardcoded, otherwise correct |
| Day start/end → UTC range | `services/attendance_service.py:77–79` | Pacific hardcoded, otherwise correct |
| "Today" as scalar UTC date | `attendance.py:121` | Broken — no range, wrong domain |
| "Today" as UTC midnight scalar | `admin.py:2495` | Broken — wrong boundary |
| Week/month bounds | `student.py:1319–1320` | Broken — UTC domain |
| Period bounds (claim enforcement) | `student.py:2028`, `admin.py:7403` | Broken — UTC domain |

---

## Prioritized Remediation Order

### Step 1 — V-005 (root fix, unblocks everything else)

Replace all 12 hardcoded `America/Los_Angeles` instantiations with `get_timezone(tz_name)` from `app/utils/time.py`. Delete module-level `PACIFIC` constants in `admin.py` and `analytics.py`. All functions that currently implicitly use Pacific must accept an explicit `tz_name` parameter or call `get_timezone()` internally. This is the prerequisite for every other fix.

### Step 2 — V-003 / V-004 (enforcement correctness)

Extract `claim_period_bounds_utc(period_key, tz_name)` into `app/utils/time.py`. Delete both local `_get_period_bounds()` functions. This fixes logic that directly affects student financial outcomes — incorrect blocking or bypassing of claim limits.

### Step 3 — V-001 (attendance accuracy)

Replace `func.date(TapEvent.timestamp) == utc_now().date()` with a UTC range query using `local_date_bounds_utc()`. Attendance reporting depends on this for correctness at any hour near the class-day boundary.

### Step 4 — V-002 (dashboard count)

One-line fix: replace `utc_now().replace(hour=0, ...)` with `local_date_bounds_utc(today_local, tz_name)[0]`.

### Step 5 — V-006, V-007 (display and analytics)

Convert `utc_now()` to class timezone before calling `.date()`, `.weekday()`, or `.month`. Low-touch, each is one or two lines.

### Step 6 — V-008 (schema correctness, after V-005)

Update all `done_for_day_date` write sites to derive the stored date from `get_timezone(tz_name)` rather than hardcoded Pacific. Evaluate whether to migrate the column to `db.DateTime(timezone=True)` for stronger schema guarantees.

### Step 7 — V-009 (filter consistency)

One-line fix in `app/__init__.py`: replace inline timezone resolution with `get_timezone()`.
