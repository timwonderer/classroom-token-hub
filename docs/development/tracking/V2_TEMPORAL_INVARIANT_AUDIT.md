# Temporal Invariant Audit

| Field | Value |
|-------|-------|
| Audit Date | 2026-04-21 |
| Specification | INV-ARC-015 v1.0 |
| Authority | `docs/development/v2_restructure_doc/INV-INVARIANT/ARCHITECTURE/INV-ARC-015_Temporal_Model_and_Boundary_Enforcement.md` |
| Status | Open — remediation not started |

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

### 🔴 V-001 — UTC date used as class-day boundary in attendance

**File:** `app/attendance.py:121` and `:139`
**Code:**
```python
today = utc_now().date()
# ...
func.date(TapEvent.timestamp) == today   # line 139
```

**Type:** Wrong temporal domain for day boundary
**Risk:** Critical
**Invariants broken:** 4, 5

**Behavior it could cause:**
`TapEvent.timestamp` is stored in UTC. `func.date(timestamp)` on a UTC timestamp returns the UTC calendar date. A student in a Pacific-time class who clocks "done for the day" at 11:00 PM Pacific (07:00 UTC next calendar day) will not match `today` — the done-for-day check silently returns `False`. Attendance reporting becomes wrong for any class active near the UTC midnight boundary (4:00 PM Pacific).

**Classification:** Must refactor

**Fix:**
```python
from app.utils.time import local_date_bounds_utc, get_timezone
tz_name = session.get("timezone")
today_local = utc_now().astimezone(get_timezone(tz_name)).date()
today_start_utc, today_end_utc = local_date_bounds_utc(today_local, tz_name)
# Replace func.date() equality with a range filter:
TapEvent.timestamp >= today_start_utc,
TapEvent.timestamp < today_end_utc,
```

---

### 🔴 V-002 — UTC midnight used as "start of today" for transaction count

**File:** `app/routes/admin.py:2495`
**Code:**
```python
Transaction.timestamp >= utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
```

**Type:** Day boundary anchored to UTC, not class timezone
**Risk:** Critical
**Invariants broken:** 5

**Behavior it could cause:**
For a Pacific-time class, UTC midnight is 4:00 PM Pacific. The dashboard "transactions today" counter resets at 4:00 PM Pacific instead of midnight, producing an incorrect count for 8 hours every day. Affects teacher reporting accuracy and any downstream logic gated on this count.

**Classification:** Must refactor

**Fix:**
```python
from app.utils.time import local_date_bounds_utc, get_timezone
tz_name = session.get("timezone")
today_start_utc, _ = local_date_bounds_utc(
    utc_now().astimezone(get_timezone(tz_name)).date(), tz_name
)
Transaction.timestamp >= today_start_utc
```

---

### 🔴 V-003 — `_get_period_bounds()` computes insurance claim windows in UTC (student route)

**File:** `app/routes/student.py:2028–2048`
**Code:**
```python
def _get_period_bounds():
    now = utc_now()
    if period_key == 'semester':
        if now.month <= 6:          # UTC month, not class-tz month
            ...
    if period_key == 'weekly':
        period_start = (now - timedelta(days=now.weekday())).replace(hour=0, ...)
        # now.weekday() is UTC weekday
```

**Type:** Period boundaries computed in wrong temporal domain
**Risk:** Critical
**Invariants broken:** 4, 5

**Behavior it could cause:**
Insurance claim period limits are enforcement logic — they cap how many claims a student can file per week/month/semester. Using UTC:
- At 11:30 PM Pacific on Sunday, UTC is already Monday. `now.weekday()` returns Monday, placing the claim in next week's window.
- A claim filed at 11:50 PM Pacific Dec 31 gets placed in the next semester (UTC Jan 1) — the wrong semester limit applies.
- Students can be incorrectly blocked from filing valid claims, or exceed their limit without the system catching it.

**Classification:** Must refactor

**Fix:**
Extract `claim_period_bounds_utc(period_key, tz_name)` into `app/utils/time.py`:
```python
def claim_period_bounds_utc(period_key: str, tz_name: str | None = None) -> tuple[datetime, datetime]:
    tz = get_timezone(tz_name)
    now_local = utc_now().astimezone(tz)
    if period_key == 'semester':
        if now_local.month <= 6:
            start = tz.localize(datetime(now_local.year, 1, 1))
            end   = tz.localize(datetime(now_local.year, 6, 30, 23, 59, 59))
        else:
            start = tz.localize(datetime(now_local.year, 7, 1))
            end   = tz.localize(datetime(now_local.year, 12, 31, 23, 59, 59))
        return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    if period_key == 'weekly':
        mon_local = now_local - timedelta(days=now_local.weekday())
        start = tz.localize(datetime(mon_local.year, mon_local.month, mon_local.day))
        end   = start + timedelta(days=7) - timedelta(seconds=1)
        return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    # monthly
    start = tz.localize(datetime(now_local.year, now_local.month, 1))
    next_month = start.replace(day=28) + timedelta(days=4)
    end = next_month.replace(day=1) - timedelta(seconds=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
```
Both routes call `claim_period_bounds_utc(period_key, tz_name)` and delete their local `_get_period_bounds()`.

---

### 🔴 V-004 — `_get_period_bounds()` duplicated in admin route (identical violation)

**File:** `app/routes/admin.py:7403–7423`
**Code:** Identical to V-003. Copy-paste of the same UTC-domain period logic.

**Type:** Period boundaries computed in wrong temporal domain
**Risk:** Critical
**Invariants broken:** 4, 5

**Behavior it could cause:**
Same as V-003, but on the admin-side insurance claim adjudication path. A claim filed in the correct period could be denied as exceeding the period limit when the admin reviews it, because the admin view and student view compute different period bounds.

**Classification:** Must refactor

**Fix:** Same as V-003 — delete this function and import `claim_period_bounds_utc` from `app/utils/time.py`.

---

### 🔴 V-005 — Hardcoded `America/Los_Angeles` across 12 call sites

**Files and lines:**

| File | Line(s) | Form |
|------|---------|------|
| `app/routes/admin.py` | 153 | `PACIFIC = pytz.timezone('America/Los_Angeles')` (module constant) |
| `app/routes/admin.py` | 8161, 8283, 9632, 9867 | `pacific = pytz.timezone('America/Los_Angeles')` (local) |
| `app/routes/analytics.py` | 36 | `PACIFIC = pytz.timezone('America/Los_Angeles')` (module constant) |
| `app/routes/api.py` | 2024, 2228, 2277, 2570 | `pacific = pytz.timezone('America/Los_Angeles')` (local) |
| `app/attendance.py` | 348 | `pacific = pytz.timezone('America/Los_Angeles')` (local) |
| `app/services/attendance_service.py` | 74 | `pacific = pytz.timezone('America/Los_Angeles')` (local) |

**Type:** Hardcoded timezone bypasses canonical `get_timezone()` — not class-scoped
**Risk:** Critical
**Invariants broken:** 1, 4, 6

**Behavior it could cause:**
INV-ARC-015 §VI.1 states each class defines a single authoritative IANA timezone. If a teacher sets their class timezone to `America/New_York` (UTC-5), every day-boundary calculation across attendance, tap-in/tap-out, done-for-day resets, and analytics runs in Pacific time (UTC-8) instead. Their school day starts at midnight New York time, but the system resets at midnight Pacific — three hours later. Students appear locked out or active for the wrong window. The system is effectively a single-timezone product despite claiming multi-timezone support.

This is the root violation. Fixing it is the prerequisite for V-001, V-002, and V-008 to collapse into the correct pattern.

**Classification:** Must refactor — all 12 sites

**Fix:**
- Delete module-level `PACIFIC` constants in `admin.py` and `analytics.py`.
- At each call site, replace `pytz.timezone('America/Los_Angeles')` with `get_timezone(tz_name)` from `app/utils/time.py`, where `tz_name` is resolved from the class record or session at request time.
- Functions that currently take no timezone argument must be updated to accept one, or call `get_timezone()` internally.

---

### 🟡 V-006 — UTC date used as default for insurance claim incident form

**File:** `app/routes/student.py:2023`
**Code:**
```python
form.incident_date.data = utc_now().date()
```

**Type:** Derived (non-UTC) date presented from UTC source
**Risk:** Medium
**Invariants broken:** 5

**Behavior it could cause:**
A student filing a claim at 11:30 PM Pacific sees tomorrow's date pre-filled, since UTC has already rolled over. If they don't notice, the incident is recorded with tomorrow's date and may fall outside claim eligibility windows.

**Classification:** Must refactor

**Fix:**
```python
tz = get_timezone(session.get("timezone"))
form.incident_date.data = utc_now().astimezone(tz).date()
```

---

### 🟡 V-007 — Analytics week/month windows use UTC weekday

**File:** `app/routes/student.py:1319–1320`
**Code:**
```python
week_start = now_utc - timedelta(days=now_utc.weekday())
month_start = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
```

**Type:** Analytics windows anchored to UTC domain
**Risk:** Medium
**Invariants broken:** 5

**Behavior it could cause:**
Student analytics ("this week" / "this month") show incorrect ranges. A student working on Sunday evening Pacific sees their hours attributed to next week because `now_utc.weekday()` has already rolled to Monday. No financial enforcement is driven by this, but it consistently misleads students about their attendance patterns.

**Classification:** Must refactor

**Fix:**
```python
tz = get_timezone(session.get("timezone"))
now_local = now_utc.astimezone(tz)
mon_local = now_local - timedelta(days=now_local.weekday())
week_start = tz.localize(datetime(mon_local.year, mon_local.month, mon_local.day)).astimezone(timezone.utc)
month_start = tz.localize(datetime(now_local.year, now_local.month, 1)).astimezone(timezone.utc)
```

---

### 🟡 V-008 — `done_for_day_date` persists a derived Pacific date

**File:** `app/models.py:1021`
**Code:**
```python
done_for_day_date = db.Column(db.Date, nullable=True)  # comment: "Pacific time"
```
**Written at:** `api.py:2287`, `admin.py:9721`, `admin.py:9870`, `attendance.py:450` — all assign a `today_pacific` derived from `utc_now().astimezone(pacific)` (itself a V-005 violation).

**Type:** Persistence of derived, non-UTC, timezone-specific date
**Risk:** Medium
**Invariants broken:** 7

**Behavior it could cause:**
The column stores a Pacific calendar date, not a UTC timestamp. Once V-005 is fixed and non-Pacific classes become operational, all `done_for_day_date` comparisons break silently — the stored date is in the wrong timezone for any non-Pacific class. The schema carries no enforcement of its Pacific-only assumption.

**Classification:** Must refactor (becomes a blocker after V-005 is resolved)

**Fix:**
Update all write sites to use `get_timezone(tz_name)` rather than the hardcoded Pacific. The column type can remain `db.Date` if it is consistently interpreted as "calendar date in the class's timezone." If stricter enforcement is needed, migrate to `db.DateTime(timezone=True)` storing the UTC start of the locked class-day.

---

### 🟡 V-009 — Jinja2 filter duplicates `get_timezone()` logic inline

**File:** `app/__init__.py:70–97`
**Code:**
```python
tz_name = session.get('timezone', 'America/Los_Angeles')
target_tz = pytz.timezone(tz_name)
# fallback also hardcodes Los Angeles
```

**Type:** Timezone resolution outside centralized logic
**Risk:** Low–Medium
**Invariants broken:** 6

**Behavior it could cause:**
If `get_timezone()` is later updated — e.g., to read from the class record instead of the session — this filter diverges silently. Timestamps displayed in templates would use a different resolution path than all business logic, causing visible inconsistencies in the UI.

**Classification:** Must refactor

**Fix:**
```python
from app.utils.time import get_timezone
target_tz = get_timezone()  # already reads session and falls back correctly
```

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

| ID | Location | Classification |
|----|----------|---------------|
| V-001 | `app/attendance.py:121,139` | Must refactor |
| V-002 | `app/routes/admin.py:2495` | Must refactor |
| V-003 | `app/routes/student.py:2028–2048` | Must refactor |
| V-004 | `app/routes/admin.py:7403–7423` | Must refactor |
| V-005 | 12 sites — hardcoded `America/Los_Angeles` | Must refactor |
| V-006 | `app/routes/student.py:2023` | Must refactor |
| V-007 | `app/routes/student.py:1319–1320` | Must refactor |
| V-008 | `app/models.py:1021` + 5 write sites | Must refactor |
| V-009 | `app/__init__.py:70–97` | Must refactor |
| V-010 | `app/routes/admin.py:1490,4133,4567,9372` | Safe to keep |
| V-011 | `tests/test_decimal_precision.py:241` | Safe to keep |

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
