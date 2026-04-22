# Temporal Enforcement Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-OPS-013      | 1.0     | 2026-04-21     | N/A        | Constitutional  |

---

## I. Purpose

Define the implementation constraints required to enforce INV-ARC-015.

This specification ensures temporal behavior cannot deviate under any execution path.

---

## II. Authority Level

Constitutional (ARC Tier). Subordinate to INV-CORE-000 and INV-ARC-015.

---

## III. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `INV-ARC-015_Temporal_Model_and_Boundary_Enforcement.md`
- `ARC-OPS-012_Datetime_Handling_Specification.md`

---

## IV. Core Enforcement Principle

> Time is constructed once per request, is immutable for that request, and cannot be sourced or recomputed elsewhere.

Any deviation is a system violation.

---

## V. Request-Time Temporal Construction

### V.1 Mandatory Construction

At request entry, before any capability evaluation:

```python
timestamp_utc = now_utc()
class_timezone = ClassConfig.get_timezone(class_id)
class_time = convert(timestamp_utc, class_timezone)

context = TemporalContext(
    timestamp_utc=timestamp_utc,
    class_timezone=class_timezone,
    class_time=class_time,
)
```

### V.2 Injection Requirement

`TemporalContext` MUST:

- Be attached to request context
- Be available to all capability checks
- Be passed explicitly into all domain commands

### V.3 Construction Constraint

- MUST occur exactly once per request
- MUST occur before any capability evaluation
- MUST occur before any domain logic executes

---

## VI. Temporal Immutability

### VI.1 Request Scope

- `TemporalContext` MUST NOT be modified after construction
- `class_time` MUST remain constant for the duration of the request

### VI.2 Cross-Request Prohibition

`TemporalContext` MUST NOT be:

- Cached
- Persisted
- Reused across requests

---

## VII. Prohibited Time Access

The following are strictly prohibited outside `TemporalContext` construction:

- `datetime.now()`
- `datetime.utcnow()`
- Any system clock access
- Any timezone conversion

### VII.1 Enforcement

CI MUST fail if:

- Prohibited APIs are used outside the approved construction module
- Time is accessed outside `TemporalContext`

---

## VIII. Timezone Source Authority

### VIII.1 Source of Truth

`class_timezone` MUST be retrieved exclusively from the Class Configuration Domain.

### VIII.2 Immutability Enforcement

- `class_timezone` MUST be write-once
- Any attempt to modify timezone MUST fail

This MUST be enforced at:

- Domain layer
- Persistence layer

---

## IX. Data Layer Constraints

### IX.1 Timestamp Storage

All timestamps MUST be stored in UTC.

### IX.2 Prohibited Storage

The following MUST NOT exist in the database schema:

- Local time fields
- Offset-based time fields
- Derived class time stored as a column

---

## X. Domain Contract

### X.1 Time Consumption

Domains MUST:

- Receive time from `TemporalContext`
- Treat it as authoritative

### X.2 Prohibited Behavior

Domains MUST NOT:

- Compute their own time
- Reinterpret timestamps
- Derive alternate temporal models

---

## XI. Temporal Boundary Enforcement

### XI.1 Boundary Definition

```
class day = [00:00, 24:00) in class timezone
```

### XI.2 Execution Constraint

All operations MUST be evaluated entirely within a single class day.

### XI.3 Violation Handling

If an operation would cross a class day boundary:

> The operation MUST be rejected before execution.

- No partial execution
- No continuation
- No splitting

---

## XII. Observability Enforcement

All time-aware logs MUST include:

```json
{
  "request_id": "...",
  "timestamp_utc": "...",
  "class_time": "...",
  "class_timezone": "..."
}
```

---

## XIII. Timezone Handling

- Timezone conversion MUST use IANA timezone rules
- Daylight Saving Time MUST be handled by the timezone library
- Custom DST logic is prohibited

---

## XIV. Test Enforcement

### XIV.1 Deterministic Time

All tests MUST:

- Inject a fixed `timestamp_utc`
- Not rely on real system time

### XIV.2 Boundary Conditions

Tests MUST include cases for:

- Just before class midnight
- Exactly at class midnight
- Just after class midnight

### XIV.3 Timezone Coverage

Tests MUST include:

- Multiple IANA timezones
- DST transition scenarios

---

## XV. Enforcement Mechanisms

The following MUST be enforced:

- Static analysis for prohibited time usage
- Runtime guards for `TemporalContext` presence
- Domain-level rejection of cross-boundary operations
- Persistence-level protection of timezone immutability

---

## XVI. Final Statement

> Time cannot be accessed implicitly.
> Time cannot be recomputed.
> Time cannot be mutated.
> Time cannot cross boundaries.

> If time is not derived from `TemporalContext`, it is invalid.

---

## XVII. Amendment

Revisions must:

1. Increment the version number.
2. Update the Effective Date.
3. Maintain alignment with INV-ARC-015.
4. Preserve all enforcement guarantees.
