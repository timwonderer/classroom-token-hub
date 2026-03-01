# Datetime Handling Specification

Classroom Economy / Classroom Token Hub

## 1. Purpose

This document defines the authoritative rules for how datetimes are created, stored, transmitted, compared, and displayed across the entire system.

The intent is not to eliminate all datetime bugs (time is chaos), but to dramatically reduce ambiguity, enforce consistency, and make violations immediately visible and diagnosable.

This specification applies to:

- Backend (Python / Flask)
- Database schema
- APIs
- Client-side JavaScript
- Templates and presentation layers

## 2. Core Invariant (Non-Negotiable)

All datetimes in the system MUST be UTC and timezone-aware.

Localization is a presentation concern only and MUST NOT affect storage, logic, or comparisons.

Any deviation from this invariant is considered a bug, not a stylistic choice.

## 3. Definitions

**UTC-aware datetime**  
A datetime object with an explicit UTC timezone (tzinfo=UTC).

**Naive datetime**  
A datetime object with no timezone information. These are considered legacy artifacts and must not be intentionally created.

**Presentation layer**  
The UI, templates, or browser rendering layer. This is the only layer where localization occurs.

## 4. Server-Side Rules (Python / Flask)

### 4.1 Datetime Creation

All “current time” values MUST be obtained through a centralized utility.

**Allowed**

```python
from app.utils.time import utc_now

utc_now()
```

**Forbidden**

```python
datetime.utcnow()        # naive
datetime.now()           # local + naive
datetime.now(tz=None)    # naive
```

Rule:  
No direct calls to `datetime.utcnow()` or `datetime.now()` are permitted anywhere in the codebase.

### 4.2 Datetime Storage (Database)

All database datetime columns MUST:

- Store values in UTC
- Be timezone-aware
- Declare intent explicitly

Required SQLAlchemy pattern:

```python
created_at = db.Column(
    db.DateTime(timezone=True),
    nullable=False,
    default=utc_now
)
```

Notes:

- `timezone=True` is mandatory.
- Defaults MUST reference `utc_now`, not inline datetime calls.
- Existing naive columns are considered technical debt and should be normalized opportunistically.

### 4.3 Datetime Normalization (Legacy Compatibility)

Legacy data or external APIs may introduce naive datetimes. These MUST be normalized before use.

A single shared normalization helper MUST be used:

```python
def ensure_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
```

Rules:

- Normalization occurs at system boundaries.
- Normalization MUST happen before comparison or serialization.
- Ad-hoc normalization logic is prohibited.

### 4.4 Datetime Comparison

**Forbidden**

```python
if now > expiry_date:
```

**Required**

```python
if utc_now() > ensure_utc(expiry_date):
```

Rule:  
All comparisons MUST occur between UTC-aware datetimes.

Any comparison capable of raising offset-naive vs offset-aware is considered a spec violation.

### 4.5 API Serialization

All datetimes returned by APIs MUST:

- Be UTC
- Be ISO 8601 compliant
- Include timezone information (Z suffix)

Example:

```json
"2026-01-12T21:45:00Z"
```

APIs MUST NOT:

- Localize timestamps
- Return browser-dependent formats
- Omit timezone information

## 5. Client-Side Rules (JavaScript)

### 5.1 Source of Truth

- The server always sends UTC timestamps  
- The client never sends localized timestamps back to the server

UTC is the only temporal language spoken across the network boundary.

### 5.2 Localization Responsibility

Localization is handled exclusively by `timezone-utils.js`.

Responsibilities include:

- Browser timezone detection
- Fallback handling
- Display formatting
- Optional session synchronization (`/api/set-timezone`)

No other client-side code may:

- Perform timezone math
- Format timestamps independently
- Assume local time semantics

### 5.3 Approved Client Utilities

All timestamp rendering MUST use:

- `TimezoneUtils.formatTimestamp`
- `TimezoneUtils.formatDate`
- `TimezoneUtils.formatTime`
- `TimezoneUtils.formatCompactDate`

Direct use of:

```javascript
new Date().toLocaleString(...)
```

outside of `timezone-utils.js` is prohibited.

## 6. Presentation Layer Rules (Templates / UI)

- Templates receive UTC timestamps or UTC strings only  
- Templates MUST NOT:  
  - Compare dates  
  - Perform timezone math  
  - Infer timezone meaning  
- Templates may only render:  
  - Pre-formatted strings  
  - `.local-timestamp` elements for client-side conversion

## 7. Error Handling & Observability

Datetime invariant violations commonly surface as:

```
TypeError: can't compare offset-naive and offset-aware datetimes
```

These errors:

- MUST be logged at ERROR level
- MUST include route and request_id
- Indicate a breach of this specification

Repeated occurrences require investigation and remediation.

## 8. Enforcement & Review

**Code Review Checklist**

- No use of `datetime.utcnow()` or `datetime.now()`
- All datetime columns use `timezone=True`
- Datetime comparisons normalize inputs
- APIs return UTC ISO 8601 timestamps
- Client rendering uses TimezoneUtils

**Social Rule**  
If you’re unsure whether a datetime is UTC-aware, assume it isn’t and normalize it.

## 9. Rationale

Time bugs are:

- Silent
- Environment-dependent
- Extremely expensive to debug

This specification:

- Eliminates ambiguity
- Centralizes responsibility
- Makes violations obvious
- Mirrors the system’s broader invariants (join_code scoping, structured logging, explicit context)

## 10. Status

This specification is active and authoritative.

Any code that violates it is considered incorrect, even if it appears to function.
