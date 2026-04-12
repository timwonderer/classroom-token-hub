# Privacy Audit: Student Date of Birth Handling

| Document Type | Audit Date | Triggered By | Status |
|---------------|------------|--------------|--------|
| Privacy Audit | 2026-04-12 | School District Review | In Progress — Brainstorm Phase |

---

## I. Purpose

This document captures a comprehensive audit of how student Date of Birth (DOB) is collected, processed, stored, and deleted throughout the Classroom Token Hub application. It was produced in response to a school district review raising concerns about the app collecting both student DOB and student names simultaneously.

The goal is not just to document *what* the system does, but *why* — understanding the design intent behind each use of DOB so that the district review can be answered accurately and so that privacy improvements can be scoped correctly.

---

## II. What DOB Actually Is in This System

The app **never stores DOB as a date**. The moment it is submitted, it is converted to an integer called **DOB_SUM**:

```
DOB_SUM = month + day + year
Example: October 10, 2008 → 10 + 10 + 2008 = 2028
```

All subsequent processing, storage, and deletion applies to this integer, not the original date. Every design decision described in this document flows from this core transformation.

---

## III. The Four Reasons DOB Is Collected

### 3.1 Student Account Claiming (Primary Use Case)

**The problem being solved:** A teacher uploads a roster before students ever interact with the app. When a student later visits and enters a join code, the system needs to confirm "are you actually the person your teacher put on this roster?" — without the teacher being present.

**The flow:**
1. Teacher uploads CSV roster → DOB_SUM computed per student and stored on the `TeacherBlock` seat record
2. Student enters: join code + first initial + last name + date of birth
3. System computes DOB_SUM from student input and compares against the seat's stored value
4. DOB_SUM is also an ingredient in the `first_half_hash` and `second_half_hash` on the seat — so name *and* DOB must both match to unlock a seat
5. On successful match, a `Student` record is created with `dob_sum` copied from the matched seat
6. Immediately after match: `TeacherBlock.dob_sum = None` (seat no longer needs it)
7. After setup completes (username + passphrase): `Student.dob_sum = None`

DOB's role here is a **one-time identity verification token** — a shared secret that only the real student would know, used once, then discarded.

**Relevant files:**
- `app/routes/student.py` lines 684–920 (claim_account route)
- `app/models.py` lines 226–296 (TeacherBlock model)
- `app/models.py` lines 298–365 (Student model)

### 3.2 Student Credential Hashing (Supporting the Claim)

DOB_SUM is used as an ingredient — alongside the student's initials and a per-seat salt — to compute the `first_half_hash` and `second_half_hash` stored on the `TeacherBlock` seat. These hashes are what the system actually compares during the claim, not the raw DOB_SUM alone. This means knowing a student's name alone is not sufficient to steal a seat — the DOB must also match.

**Relevant files:**
- `app/routes/student.py` lines 639–643 (hash computation)
- `app/hash_utils.py` (compute_primary_claim_hash, hash_hmac)

### 3.3 Username Generation (Incidental)

After a successful claim but before setup completes, `Student.dob_sum` is used to make the generated username unique and themed. The format is:

```
{adjective}{student_chosen_word}{dob_sum}{initials}
Example: bravetrees2028SK
```

The DOB_SUM integer is embedded directly in the username string. Once the username is generated, the integer is permanent in the username even though `Student.dob_sum` is later nulled.

**Key details:**
- Usernames are **never displayed to teachers or other students** — only to the claiming student, once, during setup
- The username is **never stored in plaintext** — only as HMAC-SHA256 hashes (`username_hash`, `username_lookup_hash`)
- There is no mechanism to change a username after creation
- The privacy policy does not disclose that DOB_SUM is embedded in the username format

**Relevant files:**
- `app/routes/student.py` lines 924–964 (create_username route)
- `templates/student_pin_setup.html` line 33 (only display location)

### 3.4 Teacher Account Recovery (Separate Use Case, Teachers Only)

Teachers provide their DOB at signup as a recovery authentication factor. Unlike students, the teacher DOB_SUM is:
- Immediately hashed: `HMAC-SHA256(salt, DOB_SUM)` → stored as `Admin.dob_sum_hash`
- **Never stored in plaintext**
- **Retained permanently** (by design — needed for future recovery verification)

During recovery, the teacher re-submits their DOB, which is rehashed and compared. The original date is never reconstructed.

**Relevant files:**
- `app/routes/admin.py` lines 2906–3192 (signup route, DOB hashing at line 3113)
- `app/routes/admin.py` lines 3195–3400 (recovery route, verification at line 3272)
- `app/models.py` lines 1968–2086 (Admin model, `dob_sum_hash` and `salt` columns)

---

## IV. Data Lifecycle: Complete Pipeline

```
STUDENT DOB (form input: date)
  ↓
parse_dob_input() → DOB_SUM (integer: month + day + year)
  ↓
  ├─→ TeacherBlock.dob_sum  (stored: integer, roster upload)
  │       ↓ nulled immediately at claim
  │
  ├─→ Student.dob_sum  (stored: integer, post-claim)
  │       ↓ nulled after setup completes (post-passphrase)
  │
  ├─→ first_half_hash / second_half_hash  (stored: HMAC hash on seat)
  │       used for claim verification, not reversible alone
  │
  └─→ Username string  (embedded as integer in plaintext username)
          ↓ username hashed before storage — plaintext username never stored
          but DOB_SUM persists in the hash permanently

TEACHER DOB (form input: date)
  ↓
parse_dob_input() → DOB_SUM
  ↓
HMAC-SHA256(salt, DOB_SUM) → Admin.dob_sum_hash  [permanent, irreversible]
```

---

## V. Database Columns Involved

| Table | Column | Type | Lifecycle | Notes |
|-------|--------|------|-----------|-------|
| `teacher_blocks` | `dob_sum` | Integer, nullable | Set at roster upload → Nulled at claim | Plaintext sum |
| `students` | `dob_sum` | Integer, nullable | Set at claim → Nulled post-setup | Plaintext sum, temporary |
| `admins` | `dob_sum_hash` | String(64) | Set at signup → Permanent | HMAC hash, never plaintext |
| `admins` | `salt` | LargeBinary(16) | Set at signup → Permanent | Per-user salt for hash |

---

## VI. Privacy Strengths (What the System Does Well)

1. **Non-reversible hashing for teachers** — Teacher DOB stored only as HMAC-SHA256 with per-user salt. No plaintext ever persists.
2. **Aggressive PII cleanup for students** — Two explicit nulling events: once at claim (`TeacherBlock.dob_sum = None`), once at setup completion (`Student.dob_sum = None`). Code comments document the intent explicitly.
3. **DOB_SUM not DOB** — The integer sum is structurally different from the date. It doesn't directly reveal birth month, day, or year individually.
4. **Salted credential hashes** — DOB_SUM is combined with per-seat salt when computing claim hashes, preventing cross-seat correlation.
5. **No external telemetry** — No Sentry, Datadog, Rollbar, or similar external services that could receive log data containing DOB_SUM.
6. **Username not stored in plaintext** — Only HMAC hashes of the username are stored. Even if the database is compromised, the plaintext username (containing DOB_SUM) is not directly exposed.
7. **Database traces don't capture form data** — `ActorRequestTrace` and `ErrorEvent` tables only store endpoint/method metadata, not request bodies or form fields.

---

## VII. Privacy Risks and Gaps

### Risk 1: Failed Claim Attempts Logged with DOB_SUM Values (HIGH)

**Location:** `app/routes/student.py` ~line 771–775

When a student fails to claim an account, a WARNING-level log entry is written that includes the full `match_attempts` dictionary:

```python
match_attempts.append({
    'seat_id': seat.id,
    'credential_matches': credential_matches,
    'last_name_matches': last_name_matches,
    'dob_sum_matches': dob_sum_matches,
    'seat_dob_sum': seat.dob_sum,       # ← actual DOB_SUM from roster
    'provided_dob_sum': dob_sum          # ← DOB_SUM the student typed
})

current_app.logger.warning(
    f"Claim attempt failed for join_code={join_code}, "
    f"first_initial={first_initial}, with last_name from input. "
    f"Attempted {len(match_attempts)} seat(s). Match details: {match_attempts}"
)
```

The log iterates over all unclaimed seats for the join code, meaning a single failed attempt can log DOB_SUM for an entire class roster.

**Log retention:** Rotating file handler (1MB per file, 5 backup copies, no TTL). These files persist until manually deleted or overwritten by rotation.

**Why this matters:** The privacy policy states DOB is "fully removed from the database" after claim. That is true. But logs are not the database. A student who claims their account successfully has their DOB_SUM deleted from the DB — but every failed claim attempt beforehand is preserved in log files indefinitely.

### Risk 2: DOB_SUM Permanently Embedded in Username (MEDIUM)

The format `{adjective}{word}{dob_sum}{initials}` means DOB_SUM is a permanent component of the student's username. While:
- The username is never displayed to other students or teachers
- The username is stored only as hashes in the database
- The plaintext username is shown once, on-screen, during setup

...the student is instructed to write the username down and use it for all future logins. The plaintext username (containing DOB_SUM) therefore exists on paper in the student's possession and is entered into the login form on every login.

Additionally, the privacy policy states DOB is "fully removed" after claim but does not disclose that DOB_SUM was embedded in the username before removal.

### Risk 3: DOB_SUM Reversibility Overclaimed in Privacy Policy (MEDIUM)

**Privacy policy text:** "We converted it into a long string of letters and numbers that cannot be turned back into your date of birth."

**Reality:** DOB_SUM = month + day + year. For school-age students (ages 5–18), the range of possible DOB_SUMs is approximately 1,940 (e.g., Jan 1 2010 → 2012) to 4,131 (Dec 31 2018 → 4,161). The total search space is roughly 2,200 plausible values — trivially enumerable. With the per-user salt, direct reversal requires the salt. But the statement "cannot be turned back" overclaims the protection. More accurate language: "stored in a form that does not directly reveal your birth date, but which does not provide full cryptographic protection."

For teachers, the HMAC-SHA256 hash provides genuine one-way protection (given an uncompromised salt). The overclaim primarily affects the student-facing language.

### Risk 4: Temporary Plaintext Exposure Window (LOW)

Between account claim and setup completion (typically a few minutes during a guided onboarding flow), `Student.dob_sum` exists as a plaintext integer in the database. If the database were compromised during this narrow window, DOB sums for actively-onboarding students would be exposed. This is a low-probability, low-duration risk by design.

### Risk 5: Teacher DOB Hash Retained Permanently (LOW-MEDIUM, by design)

`Admin.dob_sum_hash` is never deleted — it is needed for the teacher account recovery feature indefinitely. This is intentional and the hash is cryptographically protected (HMAC-SHA256 with per-user salt). However, it represents a longer privacy footprint for teachers than for students. A teacher who wants their account fully deleted would retain a permanent DOB hash in the system unless explicitly purged.

---

## VIII. Design Questions for Future Resolution

### Q1: Can student claim work without DOB?

DOB currently serves two roles at claim time:
1. **Disambiguation** — distinguishes between two students in the same class with matching initials (e.g., two "J. Smith"s)
2. **Identity proof** — confirms the claiming student is the person on the roster

These could be separated. Options:

| Approach | PII Eliminated | Teacher Burden | Notes |
|----------|---------------|----------------|-------|
| Teacher-issued claim codes (random, per-seat) | Complete | Small (distribute codes in class) | Cleanest privacy story; same workflow as handing out join codes |
| Student ID number | DOB replaced with district ID | Low (if IDs in upload) | Districts have governance for student IDs; less sensitive than DOB |
| Collision-only DOB | DOB collected only when name collision detected | None | Near-zero collection in practice; ~99% of students never trigger collision |
| Full last name (vs. initial) | DOB removed; last name expanded | None | Still PII, but name data is less sensitive than birth data for FERPA purposes |

### Q2: Is DOB_SUM necessary in the username?

No. The combination of a 20-adjective pool + student-chosen word + initials already generates millions of distinct usernames. DOB_SUM adds uniqueness but is not necessary for it. A random 4-digit number generated at creation time would serve the same deduplication purpose with zero PII exposure and zero functional change to any other part of the system.

### Q3: What is the district's specific concern?

The right remediation depends on what the district actually objects to:
- **Any collection of birth-related data** → claim codes or student IDs replace DOB entirely
- **Permanent retention of DOB** → current system already satisfies this once the log issue (Risk 1) is fixed
- **Privacy policy language accuracy** → documentation fix, not a code change
- **FERPA/COPPA compliance** → depends on whether DOB_SUM qualifies as "education record" or "personal information" under applicable law

---

## IX. Actionable Findings (Prioritized)

### P0 — Fix Before District Review

**1. Remove DOB_SUM from failed-claim warning logs**

`app/routes/student.py` ~line 759–775

Replace the match_attempts dict to log only non-PII diagnostics:
```python
# Instead of logging seat_dob_sum and provided_dob_sum, log:
{
    'seat_id': seat.id,
    'credential_matches': credential_matches,
    'last_name_matches': last_name_matches,
    'dob_sum_matches': dob_sum_matches
    # Remove: seat_dob_sum, provided_dob_sum
}
```
This is a one-line change per field. The diagnostic value (did DOB match or not?) is preserved; the actual values are not logged.

**2. Audit and purge existing log files**

If the app has been running in production, existing log files may contain DOB_SUM values from past failed claim attempts. These should be reviewed and purged or rotated.

### P1 — Fix Soon

**3. Replace DOB_SUM in username generation with a random number**

`app/routes/student.py` line 953

```python
# Current
username = f"{adjective}{write_in_word}{dob_sum}{initials}"

# Proposed
import random
uniquifier = random.randint(1000, 9999)
username = f"{adjective}{write_in_word}{uniquifier}{initials}"
```

This removes the embedded PII from all future usernames. Existing usernames are not affected (and would require a migration to change, which may not be worth the disruption).

**4. Update the privacy policy**

Two specific corrections needed:
- Change "cannot be turned back into your date of birth" to language that accurately describes DOB_SUM as obfuscated but not cryptographically irreversible
- Add a disclosure that a numeric component of the student's username is derived from their birth date at account creation

### P2 — Longer-Term Design Decisions

**5. Evaluate claim flow redesign**

Decide on the replacement for DOB at claim time (see Section VIII, Q1). This is the largest change and requires teacher-facing UX work (new roster upload format, code distribution, etc.).

**6. Add log retention policy**

Set a maximum retention window for application log files (e.g., 30 days) and implement automated deletion. Currently logs rotate by size with no time-based TTL.

**7. Teacher DOB deletion path**

Implement a mechanism to delete `Admin.dob_sum_hash` and `salt` if a teacher requests full account deletion. Currently the hash persists even after account removal.

---

## X. Summary Table

| Entity | What Is Stored | Format | Lifecycle | Risk |
|--------|---------------|--------|-----------|------|
| Student (TeacherBlock seat) | DOB_SUM | Plaintext integer | Upload → Nulled at claim | Low (short-lived) |
| Student (Student record) | DOB_SUM | Plaintext integer | Claim → Nulled post-setup | Low (minutes) |
| Student (username) | DOB_SUM | Embedded in username string | Created at setup → Permanent in username | Medium (permanent artifact in hashed form) |
| Teacher (Admin record) | DOB_SUM hash | HMAC-SHA256 hex | Signup → Permanent | Low (cryptographically protected) |
| Application logs | DOB_SUM | Plaintext integer in log string | On failed claim → File rotation (no TTL) | High (persists after DB cleanup) |
| Session (teacher signup) | DOB date string + sum | Plaintext in session | Duration of signup flow → Cleared after | Low (transient) |

---

## XI. Audit Participants and Method

- **Method:** Static code analysis via automated codebase exploration + manual review
- **Scope:** Full application — models, routes, forms, templates, migrations, tests, documentation
- **Files examined:** `app/models.py`, `app/routes/student.py`, `app/routes/admin.py`, `app/forms.py`, `app/hash_utils.py`, `app/__init__.py`, `app/services/tlcp.py`, all templates referencing DOB/username, all migrations referencing dob columns, `templates/privacy.html`
- **Audit date:** 2026-04-12
- **Status:** Brainstorm/findings phase — remediation not yet implemented

---

*This document should be updated as remediation items are completed. Mark each item in Section IX with the completion date and commit reference.*
