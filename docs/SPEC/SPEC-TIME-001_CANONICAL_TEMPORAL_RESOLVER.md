# SPEC-TIME-001: Canonical Temporal Resolver

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-TIME-001 | 1.3 | 2026-10-24 | 1.2 | Implementation Spec |

---

## I. Purpose

This document is the normative build specification for `canonical_temporal_resolver`, the single Canonical Temporal Evaluation tool required by `INV-ARC-015`.

It defines the runtime object, public primitives, inputs, return contract, fail-closed behavior, and browser-facing timezone contract for all temporal evaluation in Classroom Token Hub.

This specification replaces the historical temporal rebuild plan. The old plan described a broad target architecture; this document defines the concrete resolver that all DOM specifications, FEAT specifications, runtime services, scheduled jobs, route handlers, and tests must use.

`canonical_temporal_resolver` is the only public temporal evaluation helper. Older helper names are deprecated and must not be used as new domain or FEAT dependencies.

---

## II. Authority

This specification is subordinate to:

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`

If this document conflicts with `INV-ARC-015`, `INV-ARC-015` prevails.

---

## III. Core Principle

`canonical_temporal_resolver` measures and evaluates time. Domains interpret the resulting temporal truth according to their own business rules.

Examples:

- PROD decides which productivity intervals are compensable; the resolver measures the exact elapsed seconds.
- OBL decides which assessment boundary applies; the resolver resolves whether the boundary has passed.
- The browser displays time in the canonical timezone supplied by the resolver; the browser does not make authoritative temporal decisions.

The resolver must remain business-blind. It must not contain payroll, obligation, hall-pass, store, banking, insurance, or attendance-specific logic.

---

## IV. Evaluation Types

Every resolver call must declare one evaluation type.

| Type | Name | Temporal Authority | Required Context |
| --- | --- | --- | --- |
| `SLE` | System-Level Evaluation | UTC | None |
| `CLE` | Class-Level Evaluation | Canonical Class Timezone | `CanonicalContext` with `class_id` |

### SLE

System-Level Evaluations are platform/user-system evaluations whose authority is UTC.

Examples:

- session expiry
- observability
- account inactivity
- system logs

### CLE

Class-Level Evaluations are class-scoped evaluations whose authority is the class's Canonical Class Timezone.

Examples:

- productivity and payroll
- obligation due dates
- hall-pass timing
- store item expiry
- class-local day boundaries

For CLE, the resolver must fail closed if the canonical class timezone cannot be established.

---

## V. Temporal Authority Resolution

The resolver must use one deterministic authority flow:

1. Accept evaluation type.
2. If `SLE`, set temporal authority to UTC.
3. If `CLE`, require canonical execution context.
4. Resolve Canonical Class Timezone from `ctx.class_id`.
5. Validate that the timezone is a valid IANA timezone.
6. Normalize all supplied timestamps into the resolved temporal authority.
7. Execute the requested primitive.
8. Return a canonical temporal evaluation object.

For architectural consistency, every CLE primitive evaluates in Canonical Class Timezone, even when the calculation would be mathematically equivalent in UTC.

No CLE primitive may operate directly on raw UTC timestamps after authority resolution.

---

## VI. Storage and Input Rules

All persisted timestamps remain UTC.

The resolver may accept UTC-aware timestamps from persistence, but callers must not independently convert them to class-local time before calling the resolver.

The resolver must reject or normalize inputs as follows:

| Input Condition | Required Behavior |
| --- | --- |
| UTC-aware timestamp | Accept |
| timezone-aware non-UTC timestamp | Normalize through temporal authority |
| naive timestamp | Reject unless the specific test-only pathway explicitly supplies authority |
| missing required timestamp | Fail closed |
| invalid interval with end before start | Fail closed |
| unknown timezone for CLE | Fail closed |
| missing `ctx.class_id` for CLE | Fail closed |

---

## VII. Canonical Return Object

Every primitive returns a `CanonicalTemporalEvaluation` object.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `evaluation_type` | `SLE` or `CLE` | Evaluation category |
| `temporal_authority` | string | `UTC` for SLE or IANA timezone for CLE |
| `canonical_now` | datetime | Current timestamp in the resolved authority |
| `canonical_now_utc` | datetime | Same instant in UTC for persistence/correlation |
| `reference_time_utc` | datetime | UTC timestamp used as the evaluation anchor |
| `class_id` | string or null | Class boundary for CLE |
| `result` | primitive-specific | Boolean, timestamp boundary, date, or duration result |

The object may expose typed convenience properties for primitive-specific results, but those properties must not introduce business semantics.

Examples:

- `is_earlier`
- `is_later`
- `is_between`
- `elapsed_seconds`
- `remaining_seconds`
- `evaluation_date`
- `boundary_start`
- `boundary_end`
- `period`
- `shifted_timestamp`
- `shifted_timestamp_utc`
- `display_timezone`

---

## VIII. Required Public API

The implementation must expose one entry point:

```python
canonical_temporal_resolver(
    evaluation_type: str,
    *,
    canonical_execution_context: CanonicalContext | None = None,
    primitive: str,
    reference_time_utc: datetime | None = None,
    **primitive_inputs,
) -> CanonicalTemporalEvaluation
```

Constants:

```python
SYSTEM_LEVEL_EVALUATION = "SLE"
CLASS_LEVEL_EVALUATION = "CLE"
```

Permitted primitive names:

- `current_time`
- `earlier_than`
- `later_than`
- `same_instant`
- `between_boundaries`
- `time_since`
- `time_until`
- `current_evaluation_day`
- `evaluation_day_boundaries`
- `evaluation_period_boundaries`
- `elapsed_duration`
- `shift_timestamp`
- `anchored_recurrence_boundary`
- `minimum_period_duration`
- `shift_calendar_days`
- `localize_timestamp`

The resolver must not expose additional public temporal primitives without amending this spec.

---

## IX. Primitive Contracts

### 1. `current_time`

Purpose:

Resolve canonical "now" under the selected temporal authority.

Accepts:

| Input | Required | Notes |
|---|---|---|
| `reference_time_utc` | No | If omitted, resolver obtains current UTC time internally |

Returns:

| Result Field | Meaning |
| --- | --- |
| `canonical_now` | Current timestamp in the resolved temporal authority |
| `canonical_now_utc` | Same instant in UTC |
| `display_timezone` | Timezone browser may use for display |

Rules:

- Callers must not call `datetime.now()` independently.
- Browser display may use `display_timezone`, but browser time is not authoritative.

### 2. `earlier_than`

Purpose:

Determine whether one timestamp is earlier than another under canonical temporal authority.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `candidate` | Yes | Timestamp being evaluated |
| `reference` | Yes | Timestamp being compared against |

Returns:

| Result Field | Meaning |
|---|---|
| `is_earlier` | `candidate < reference` |

### 3. `later_than`

Purpose:

Determine whether one timestamp is later than another under canonical temporal authority.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `candidate` | Yes | Timestamp being evaluated |
| `reference` | Yes | Timestamp being compared against |

Returns:

| Result Field | Meaning |
|---|---|
| `is_later` | `candidate > reference` |

### 4. `between_boundaries`

Purpose:

Determine whether a timestamp falls inside a canonical temporal window.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `candidate` | Yes | Timestamp being evaluated |
| `start_boundary` | Yes | Inclusive start boundary |
| `end_boundary` | Yes | Exclusive end boundary |

Returns:

| Result Field | Meaning |
|---|---|
| `is_between` | `start_boundary <= candidate < end_boundary` |

Rules:

- Boundary semantics are always inclusive start, exclusive end.
- Callers must not implement alternate inclusion rules locally.

### 5. `time_since`

Purpose:

Measure exact elapsed time from a supplied timestamp until canonical now.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `start` | Yes | Starting timestamp |
| `reference_time_utc` | No | Evaluation anchor; if omitted, resolver obtains current UTC time internally |

Returns:

| Result Field | Meaning |
|---|---|
| `elapsed_seconds` | Exact integer elapsed seconds from `start` to canonical now |

Rules:

- Negative elapsed time fails closed.
- No rounding is performed.

### 6. `time_until`

Purpose:

Measure exact remaining time from canonical now until a supplied timestamp.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `target` | Yes | Target timestamp |
| `reference_time_utc` | No | Evaluation anchor; if omitted, resolver obtains current UTC time internally |

Returns:

| Result Field | Meaning |
|---|---|
| `remaining_seconds` | Exact integer seconds from canonical now to `target` |

Rules:

- Negative remaining time is returned as `0` only if the caller explicitly requests clamping through a future spec amendment. Version 1.0 fails closed on negative values.
- No rounding is performed.

### 7. `current_evaluation_day`

Purpose:

Derive the current calendar day under the selected temporal authority.

Accepts:

| Input | Required | Notes |
|---|---|---|
| `reference_time_utc` | No | Evaluation anchor; if omitted, resolver obtains current UTC time internally |

Returns:

| Result Field | Meaning |
|---|---|
| `evaluation_date` | Calendar date in the resolved authority |

Rules:

- For CLE, the evaluation date is the class-local date.
- For SLE, the evaluation date is the UTC date.

### 8. `evaluation_day_boundaries`

Purpose:

Derive canonical start/end boundaries for an evaluation day.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `evaluation_date` | No | If omitted, derive current evaluation day |
| `reference_time_utc` | No | Used only when `evaluation_date` is omitted |

Returns:

| Result Field | Meaning |
| --- | --- |
| `boundary_start` | Start of evaluation day in resolved authority |
| `boundary_end` | End of evaluation day in resolved authority |
| `boundary_start_utc` | Start boundary converted to UTC for DB queries |
| `boundary_end_utc` | End boundary converted to UTC for DB queries |

Rules:

- Day boundary is `[00:00, 24:00)` in the resolved authority.
- Callers must not derive day boundaries independently.

### 9. `elapsed_duration`

Purpose:

Measure exact elapsed duration across one or more timestamp intervals.

Accepts:

| Input | Required | Notes |
|---|---|---|
| `intervals` | Yes | List of `(start, end)` timestamp pairs |

Returns:

| Result Field | Meaning |
|---|---|
| `elapsed_seconds` | Exact sum of elapsed seconds across all intervals |

Rules:

- The caller selects which intervals have business meaning.
- The resolver only validates and measures the intervals.
- Each interval must have `end >= start`.
- The intervals are summed exactly and the total is truncated to whole seconds once. Truncating each interval would drop up to a second per interval.
- Empty interval lists fail closed unless a future spec amendment explicitly allows zero-duration evaluation.
- Overlapping intervals fail closed in version 1.0 to prevent accidental double counting.
- Adjacent intervals are allowed.
- No rounding is performed.

Example:

```text
Input intervals:
08:00:00 -> 08:20:00
08:30:00 -> 09:00:22

Output:
elapsed_seconds = 3022
```

PROD prices the seconds as they are: payroll defines no time rounding (`DOM-PROD-001` §XV.3; operator ruling 2026-09-30). Any business rounding a domain might define belongs to that domain.

`canonical_temporal_resolver` must not perform business rounding.

### 10. `shift_timestamp`

Purpose:

Construct a new timestamp by shifting a supplied timestamp by an exact elapsed duration.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `timestamp` | Yes | Timestamp being shifted |
| `elapsed_seconds` | Yes | Signed integer number of seconds to shift |

Returns:

| Result Field | Meaning |
| --- | --- |
| `shifted_timestamp` | Shifted timestamp in the resolved temporal authority |
| `shifted_timestamp_utc` | Same shifted instant converted to UTC for persistence/correlation |

Rules:

- The caller decides what business event requires a shifted timestamp.
- The resolver only normalizes the timestamp, applies the exact second shift, and returns canonical authority-local and UTC forms.
- `elapsed_seconds` must be an integer.
- No business rounding, payroll policy, obligation policy, or display formatting is performed.

Example:

```text
Input:
timestamp = active productivity start
elapsed_seconds = remaining daily-limit seconds

Output:
shifted_timestamp_utc = exact inactive-event timestamp that makes the active duration equal the class limit
```

PROD may use this primitive to construct the exact close-out timestamp for scheduled daily-limit enforcement, but the resolver must not know what a daily limit is.

### 11. `evaluation_period_boundaries`

Purpose:

Derive canonical start/end boundaries for a calendar period under the selected temporal authority.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `period` | Yes | `day`, `week`, or `month` |
| `reference_time_utc` | No | If omitted, resolver obtains current UTC time internally |

Returns:

| Result Field | Meaning |
| --- | --- |
| `period` | Normalized period name |
| `boundary_start` | Start of the period in resolved authority |
| `boundary_end` | Exclusive end of the period in resolved authority |
| `boundary_start_utc` | Start boundary converted to UTC for DB queries |
| `boundary_end_utc` | End boundary converted to UTC for DB queries |

Rules:

- `day` boundaries are `[00:00, 24:00)` in the resolved authority.
- `week` boundaries are Monday-start calendar weeks in the resolved authority.
- `month` boundaries are calendar-month boundaries in the resolved authority.
- Callers must not derive week or month boundaries independently.
- The resolver does not decide whether a weekly or monthly period has business meaning.

### 12. `anchored_recurrence_boundary`

Purpose:

Derive the n-th boundary of a recurrence anchored to a calendar date, such as a recurring billing period that repeats on the anchor day each month or every seven days.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `anchor_date` | Yes | Calendar date in the resolved authority that anchors the recurrence |
| `cadence` | Yes | `week` or `month` |
| `index` | Yes | Integer `n ≥ 0`; `0` returns the anchor itself |
| `overflow` | For `month` | `roll_forward` or `clamp`; how to treat an anchor day that does not exist in the target month |

Returns:

| Result Field | Meaning |
| --- | --- |
| `boundary_date` | Calendar date of the n-th boundary in the resolved authority |
| `boundary_start` | Start of that date (00:00) in the resolved authority |
| `boundary_start_utc` | Same instant in UTC, for persistence and comparison |

Rules:

- Every boundary is derived independently from `anchor_date` and `index`. It is never derived from a previously returned boundary, so a rolled or clamped boundary never changes the anchor or drifts later boundaries.
- `week`: the boundary date is `anchor_date + 7 × index` calendar days. It is not `168 × index` elapsed hours; DST transitions do not move it off midnight.
- `month`: the target month is `index` calendar months after the anchor's month. If the anchor's day exists in the target month, that date is the boundary. Otherwise:
  - `roll_forward`: the boundary is the first day of the following month (the next date that exists);
  - `clamp`: the boundary is the last day of the target month.
- Boundaries are at `00:00` in the resolved authority. Periods between consecutive boundaries are half-open `[boundary_n, boundary_{n+1})`.
- The caller chooses `overflow`. The resolver performs calendar arithmetic only and does not know which business rule a product has ratified.

Required example (`anchor_date` = January 31, `month`, `roll_forward`), indexes 0–11 of a non-leap year:

```text
1/31 → 3/1 → 3/31 → 5/1 → 5/31 → 7/1 → 7/31 → 8/31 → 10/1 → 10/31 → 12/1 → 12/31
```

In a leap year index 1 is still March 1 (February 31 does not exist; February 29 is not the anchor day).

### 13. `minimum_period_duration`

Purpose:

Report the shortest possible period between consecutive boundaries of a cadence, so that product rules bounded by period length (for example a bill preview interval) are validated against the calendar rather than a constant copied into each product.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `cadence` | Yes | `week` or `month` |

Returns:

| Result Field | Meaning |
| --- | --- |
| `minimum_calendar_days` | `7` for `week`; `28` for `month` |

Rules:

- The value is the minimum over every anchor day and every month under either overflow rule. For `month` the minimum is a February period, 28 days.
- A product rule of the form `0 < x < minimum_period_duration(cadence)` holds for every period of that cadence.

### 14. `shift_calendar_days`

Purpose:

Move a calendar date, or a timestamp's local date, by whole calendar days in the resolved authority. A calendar day is 23, 24 or 25 elapsed hours, so `N` days is never `N × 24` hours.

Accepts exactly one of `date` or `timestamp`:

| Input | Required | Notes |
| --- | --- | --- |
| `date` | One of | A calendar date in the resolved authority (a `date`, not a `datetime`) |
| `timestamp` | One of | A timezone-aware timestamp |
| `days` | Yes | Signed integer number of calendar days |
| `time` | No | With `date` only: a naive local time of day. The result then also carries `shifted_timestamp` at that wall-clock time on `shifted_date` |

Returns:

| Result Field | Meaning |
| --- | --- |
| `shifted_date` | The calendar date `days` days after the source date in the resolved authority |
| `boundary_start` / `boundary_start_utc` | For `date`: `00:00` of `shifted_date` in the resolved authority, and the same instant in UTC |
| `shifted_timestamp` / `shifted_timestamp_utc` | For `timestamp`: the same local wall-clock time on `shifted_date`. For `date` with `time`: that wall-clock time on `shifted_date`. Each with the same instant in UTC |

Rules:

- A `timestamp` keeps its local wall-clock time, and a `date` with `time` takes that wall-clock time. Where the time occurs twice (a fall-back fold), the earlier instant is taken; where it does not occur (a spring-forward gap), the smallest forward shift onto an existing time is taken.
- The caller decides what the shift means (a claim window, a waiting period, a grace period, a schedule). The resolver performs calendar arithmetic only.
- `days` must be an integer; supplying both or neither of `date` and `timestamp` fails closed.

### 15. `localize_timestamp`

Purpose:

Express a supplied timestamp in the resolved temporal authority, for display or to read its local calendar date.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `timestamp` | Yes | A timezone-aware timestamp |

Returns:

| Result Field | Meaning |
| --- | --- |
| `local_timestamp` | The same instant in the resolved authority |
| `evaluation_date` | Its calendar date in the resolved authority |

Rules:

- This is the only sanctioned timezone conversion outside the resolver. Callers must not call `astimezone`, `localize`, `pytz.timezone` or `ZoneInfo`.


### 16. `same_instant`

Purpose:

Determine whether two timestamps are the same instant.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `candidate` | Yes | Timestamp being evaluated |
| `reference` | Yes | Timestamp being compared against |

Returns:

| Result Field | Meaning |
|---|---|
| `is_same` | `candidate` and `reference` are the same instant, whatever offsets they carry |

---

## X. Browser Timezone Contract

`canonical_temporal_resolver` is responsible for resolving and supplying the authoritative display timezone.

| Surface | Display Timezone |
| --- | --- |
| SLE page or system surface | `UTC` |
| CLE page or class-scoped surface | Canonical Class Timezone |

The browser may use the supplied timezone to render and continuously update visual clocks.

The browser must not use its displayed clock to decide business truth.

Server-rendered pages follow `INV-ARC-022` §V.8 and `SPEC-UI-001` §VI–§X, both of which govern this
specification: a page's builder produces every displayed time as presentation-ready text, localizing
through `localize_timestamp` (or the boundary primitives) with the page's context, and the template
prints that text. A template never formats, converts or derives a time (no time filters, `strftime`,
`isoformat` or `astimezone`), and nothing queries the database while a template renders.
`tests/test_INV_ARC_022__templates_do_not_format_time.py` enforces this over `templates/`.

Allowed:

```text
Server supplies display_timezone = America/Los_Angeles.
Browser renders navbar clock in America/Los_Angeles.
```

Forbidden:

```text
Browser decides whether payroll is due from local device time.
Browser decides whether an obligation deadline passed from local device time.
Browser computes class-local day boundaries.
```

---

## XI. Domain Boundary Rules

### PROD

PROD owns:

- which productivity events are active or inactive;
- which intervals count as compensable;
- how exact elapsed seconds become payable minutes under payroll policy.

The resolver owns:

- measuring the supplied intervals;
- resolving class-local day and boundary truth;
- providing exact elapsed seconds.

### OBL

OBL owns:

- which obligation assessment boundary applies;
- which period or cycle has business meaning;
- whether an assessment is due.

The resolver owns:

- resolving the temporal boundary;
- comparing timestamps;
- calculating exact elapsed or remaining time.

### LED

Ledger owns monetary time only as recorded occurrence/provenance timestamps. Ledger must use `canonical_temporal_resolver` for temporal comparisons, reconciliation cutoffs, and display timezone metadata, but Ledger must not encode business-specific temporal semantics.

---

## XII. Prohibited Patterns

The following are prohibited outside `canonical_temporal_resolver`:

- `datetime.now()`
- `datetime.utcnow()`
- raw `end - start` duration math
- direct comparison of two timestamps to make a decision (`a < b`, `a == b`): use `earlier_than`, `later_than`, `between_boundaries` or `same_instant`. Ordering a collection by its timestamps (`sorted`, `min`, `max`) is not a decision and may compare directly (owner ruling 2026-10-24)
- direct timezone conversion
- raw `.date()` derivation for business logic
- local day-boundary construction
- hardcoded `America/Los_Angeles`
- browser/device-local business evaluation
- FEAT-local current-time reads
- test-local current-time reads for domain behavior

Tests must inject `reference_time_utc` into `canonical_temporal_resolver` rather than relying on wall-clock time.

---

## XIII. Implementation Location

The canonical implementation must live at:

```text
app/utils/canonical_temporal_resolver.py
```

The public names exported by this module must include:

```python
SYSTEM_LEVEL_EVALUATION
CLASS_LEVEL_EVALUATION
CanonicalTemporalEvaluation
canonical_temporal_resolver
```

`canonical_temporal_resolver` may call any lower-level time utility it requires, including functions in `app/utils/time.py`.

No code outside `app/utils/canonical_temporal_resolver.py` may call `app/utils/time.py` or any other time tool directly for temporal behavior. All runtime code, tests, DOM logic, FEAT logic, route logic, scheduled jobs, service code, model defaults, and template/page context builders must obtain temporal values through `canonical_temporal_resolver`.

`app/utils/time.py` is an internal implementation dependency of the resolver, not a public application API.

The resolver module's `utc_now()` is its own wall clock: the source of `current_time` when no `reference_time_utc` is supplied, and the single seam tests patch to pin time. Application code must not import or call it; it obtains "now" from the `current_time` primitive. The module exports no other temporal helper: `ensure_utc` and `advance_local_calendar_days` were removed in version 1.3 (the latter became `shift_calendar_days`).

A SQLAlchemy column `default` / `onupdate` needs a callable; one private callable in `app/models.py` that returns `current_time`'s `canonical_now_utc` is the only permitted wrapper. Every other temporal value is obtained by calling `canonical_temporal_resolver` at the point of use: a private function whose body only forwards to the resolver (`_now()`, `_is_later()`, `_class_local_date()`) is a wrapper and is not permitted. A function that applies a domain rule and uses the resolver to do it (a session idle timeout, "has this period begun") is domain logic, not a wrapper.

Deprecated names include any prior temporal helper, temporal context, or temporal module name not routed through `canonical_temporal_resolver`.

Historical documents and migration notes may mention older names, but new implementation, tests, DOM specs, and FEAT specs must use `canonical_temporal_resolver`.

---

## XIV. Test Requirements

Targeted tests must prove:

1. SLE resolves to UTC.
2. CLE resolves to Canonical Class Timezone.
3. CLE fails closed without class context.
4. CLE fails closed when class timezone cannot be established.
5. `current_time` returns UTC and authority-local forms of the same instant.
6. `earlier_than` and `later_than` normalize through the selected authority.
7. `between_boundaries` uses inclusive-start/exclusive-end semantics.
8. `time_since` returns exact elapsed seconds.
9. `time_until` returns exact remaining seconds.
10. `current_evaluation_day` derives class-local day for CLE.
11. `evaluation_day_boundaries` returns both authority-local and UTC boundaries.
12. `elapsed_duration` sums one interval.
13. `elapsed_duration` sums multiple discontinuous intervals.
14. `elapsed_duration` rejects end-before-start intervals.
15. `elapsed_duration` rejects overlapping intervals.
16. `shift_timestamp` returns authority-local and UTC forms of the same shifted instant.
17. `evaluation_period_boundaries` returns day/week/month authority-local and UTC boundaries.
18. Payroll-style rounding is not performed by the resolver.
19. Browser display timezone is `UTC` for SLE.
20. Browser display timezone is Canonical Class Timezone for CLE.
21. `anchored_recurrence_boundary` reproduces the required day-31 `roll_forward` sequence, in a leap and a non-leap year.
22. `anchored_recurrence_boundary` distinguishes itself from a fixed-duration period, from end-of-month clamping (under `roll_forward`), and from deriving each boundary from the previous result.
23. `anchored_recurrence_boundary` weekly boundaries stay at class-local midnight across a DST transition.
24. `minimum_period_duration` returns 7 for `week` and 28 for `month`.
25. `shift_calendar_days` moves a date by calendar days to local midnight across a DST transition, and places a supplied local time on the shifted date.
26. `shift_calendar_days` keeps a timestamp's local wall-clock time across a DST transition.
27. `shift_calendar_days` takes the earlier instant in a fold and shifts forward out of a gap.
28. `shift_calendar_days` fails closed on non-integer `days`, on both or neither source, and on naive or wrong-typed sources.
29. `localize_timestamp` returns the instant in the resolved authority and its local date, and rejects a naive timestamp.
30. `same_instant` compares instants regardless of offset and rejects a naive timestamp.
31. `elapsed_duration` sums intervals exactly and truncates the total once.

A structural guard enforces §XII and §XIII over `app/`: `tests/test_SPEC_TIME_001__resolver_is_the_only_time_tool.py`, with its detector in `tests/guards/temporal_resolver_conformance.py` and a mutation proof for each prohibited pattern. It must fail when it scans fewer files than `app/` holds; its predecessor scanned a path that no longer existed and passed while checking nothing.

Recommended test file:

```text
tests/dom/temporal/test_SPEC_TIME_001__canonical_temporal_resolver.py
```

---

## XV. Migration Rules

When migrating existing code:

1. Replace every direct call to `app/utils/time.py` outside `app/utils/canonical_temporal_resolver.py` with `canonical_temporal_resolver(...)`.
2. Keep `app/utils/time.py` only as an internal lower-level implementation dependency of the resolver.
3. Do not add compatibility wrappers that preserve old direct temporal APIs for any application caller.
4. Update FEAT specs to cite `SPEC-TIME-001` where they depend on temporal evaluation.
5. Add targeted tests before rewiring route/template surfaces that depend on temporal behavior.

---

## XVI. Definition of Done

`SPEC-TIME-001` is implemented when:

- `app/utils/canonical_temporal_resolver.py` exists and exports the required public names;
- all required primitives are implemented;
- CLE/SLE authority resolution is deterministic;
- every primitive returns `CanonicalTemporalEvaluation`;
- no code outside `app/utils/canonical_temporal_resolver.py` imports or calls `app/utils/time.py` or other time tools directly;
- domain/FEAT temporal behavior stops doing direct datetime math;
- targeted tests pass;
- PROD payroll can call `elapsed_duration` and receive exact elapsed seconds;
- OBL can call boundary primitives and receive canonical class-local boundaries;
- browser-facing request/page context can obtain display timezone from the resolver.

---

## XVII. Amendment

**Version 1.3 (2026-10-24):** adds `shift_calendar_days` (§IX.14; owner ruling 2026-10-24) `localize_timestamp` (§IX.15) and `same_instant` (§IX.16) (owner rulings 2026-10-24). Moving a date by an arbitrary number of calendar days and expressing a timestamp in the authority had no primitive, so callers did it with `timedelta`, `astimezone` and `.date()`. §XIII names the resolver's `utc_now()` as its internal clock and test seam, removes `ensure_utc` and `advance_local_calendar_days` from the module's exports, and permits one private column-default callable in `app/models.py`. §IX.9: `elapsed_duration` sums exactly and truncates once (owner ruling 2026-10-24). §XII: a decision may not compare two timestamps directly; ordering may (owner ruling 2026-10-24). §XIII: private helpers that only wrap a resolver call are not permitted in application code (owner ruling 2026-10-24). §X: server-rendered times are produced by page builders, never in templates (`INV-ARC-022` §V.8, `SPEC-UI-001`; owner ruling 2026-10-25 by authority). §XIV adds tests 25–31 and the structural guard. Found 2026-10-24: 464 prohibited operations in 72 application files, undetected because the previous guard scanned a non-existent directory.

Revisions to this document must:

1. Increment the version number.
2. Update the effective date.
3. Remain subordinate to `INV-ARC-015`.
4. Preserve the finite primitive model unless `INV-ARC-015` is amended first.
5. Distinguish temporal measurement from business interpretation.
