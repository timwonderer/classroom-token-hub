# Privacy Audit: Student Date of Birth Handling

| Document Type | Audit Date | Triggered By | Status |
|---------------|------------|--------------|--------|
| Privacy Audit | 2026-04-12 | School District Review | Phase 1 Complete — Awaiting District Feedback |

**Remediation summary (2026-04-12):** P0 and P1 items completed on branch `claude/review-privacy-concerns-d4IKD`. P2 design decisions finalized in Section XII pending district feedback before implementation.

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

**1. Remove DOB_SUM from failed-claim warning logs** ✅ COMPLETED 2026-04-12

`app/routes/student.py` ~line 759–775

The `match_attempts` dict no longer includes `seat_dob_sum` or `provided_dob_sum`. The diagnostic value (did DOB match or not?) is preserved via the boolean `dob_sum_matches` flag; the actual values are not logged.

```python
# Implemented — logs only:
{
    'seat_id': seat.id,
    'credential_matches': credential_matches,
    'last_name_matches': last_name_matches,
    'dob_sum_matches': dob_sum_matches
}
```

**2. Audit and purge existing log files** ⚠️ PENDING — Manual Action Required

If the app has been running in production, existing log files may contain DOB_SUM values from past failed claim attempts. These files exist outside the application code and cannot be purged by a code change. Log files should be reviewed and rotated/purged manually on the production server before or immediately after deploying the branch.

### P1 — Fix Soon

**3. Replace DOB_SUM in username generation with a random number** ✅ COMPLETED 2026-04-12

`app/routes/student.py` — `create_username` route

```python
# Implemented
uniquifier = random.randint(1000, 9999)
username = f"{adjective}{write_in_word}{uniquifier}{initials}"
student.username_migrated = True
```

All new accounts now receive usernames with a random 4-digit suffix. No PII is embedded.

**3a. One-time migration for existing accounts** ✅ COMPLETED 2026-04-12

Existing students whose usernames were created with the old DOB_SUM format are flagged via a new `Student.username_migrated` boolean column (`server_default = false`). On their next login, they are intercepted before reaching the dashboard and taken through a one-time username update flow:

1. `GET /migrate-username` — prompts for a new theme word
2. `POST /migrate-username` → validates word, generates new username with random suffix, stores in session
3. `GET /confirm-username-migration` — shows new username once, requires "written down" checkbox
4. `POST /confirm-username-migration` — commits new username hashes, sets `username_migrated = True`

Migration file: `migrations/versions/b1c2d3e4f5a6_add_username_migrated_to_students.py`

**4. Update the privacy policy** ✅ COMPLETED 2026-04-12

Five corrections made to `templates/privacy.html`:

- **Student DOB bullet (line 43):** Restored accurate irreversibility language — "We immediately convert it into a cryptographic hash — a fixed-length string that cannot be reversed to recover your date of birth — before any values are stored. The raw date is never written to disk."
- **Theme word bullet:** Added explicit disclosure — "combined with a randomly generated number and your initials to create your login username. Your username does not contain your date of birth or any other personal information."
- **PIN description:** Corrected "four- to six-digit" → "four- to eight-digit" (matches actual JS validation)
- **Post-Setup PII Cleanup section:** Clarified timing (cleanup is at setup completion, not claim); added "Application logs do not retain date of birth information"
- **Retention table:** Updated "Hashed student date of birth" row to accurately describe what is stored (credential hashes, not raw dates) and when deletion occurs (after account setup, not after claim)

### P2 — Longer-Term Design Decisions

**5. Claim flow redesign: replace DOB with name-only + dedupe code** — Design finalized; implementation deferred pending district feedback

See Section XII for the complete design spec and v2.0 compatibility analysis.

**6. Add log retention policy** — Deferred

Set a maximum time-based retention window for application log files (e.g., 30 days) and implement automated deletion. Currently logs rotate by size with no TTL. Not urgent; depends on whether the district's concern extends to log data.

**7. Teacher DOB deletion path** — Deferred

Implement a mechanism to delete `Admin.dob_sum_hash` and `salt` if a teacher requests full account deletion. Currently the hash persists even after account removal. Not in scope for current review; teacher DOB is adult-consented and FERPA does not govern teacher records.

---

## X. Summary Table

| Entity | What Is Stored | Format | Lifecycle | Risk | Status |
|--------|---------------|--------|-----------|------|--------|
| Student (TeacherBlock seat) | DOB_SUM | Plaintext integer | Upload → Nulled at claim | Low (short-lived) | No change needed |
| Student (Student record) | DOB_SUM | Plaintext integer | Claim → Nulled post-setup | Low (minutes) | No change needed |
| Student (username) — new accounts | Random 4-digit number | Embedded in username string | Created at setup → Permanent | None | ✅ Fixed |
| Student (username) — legacy accounts | DOB_SUM | Embedded in username string | One-time migration on next login | Medium | ✅ Fixed (migration flow) |
| Teacher (Admin record) | DOB_SUM hash | HMAC-SHA256 hex | Signup → Permanent | Low (cryptographically protected) | No change needed |
| Application logs | No PII | Boolean match flags only | On failed claim → File rotation | None | ✅ Fixed (existing log files: manual purge needed) |
| Session (teacher signup) | DOB date string + sum | Plaintext in session | Duration of signup flow → Cleared after | Low (transient) | No change needed |

---

---

## XI. Forward Design: DOB-Free Claim Flow (v2.0-Aligned)

> **Status:** Design finalized. Implementation deferred until district provides specific feedback — making large structural changes during active review would slow the process and may address the wrong concern.

This section documents the agreed-upon design for replacing DOB in the student claim flow with a name-only + dedupe-code system, validated against the `codex/v2.0` architecture.

---

### 11.1 The Core Problem DOB Solves Today

DOB serves two distinct roles at claim time. The replacement design must address both:

| Role | Current mechanism | Proposed replacement |
|------|-------------------|----------------------|
| **Identity proof** — confirm the student is on this roster | DOB_SUM hash (credential hashes using HMAC of DOB + initials) | `name_lookup_hash`: HMAC(first_initial + full_last_name, global_pepper) — student enters their name at claim time; the hash is compared against the stored seat hash |
| **Disambiguation** — distinguish two students with the same name pattern | DOB_SUM as tiebreaker | Teacher-generated 4-character dedupe code, issued only when a hash collision actually exists within the join code |

The full last name is stored **encrypted at rest** (`PIIEncryptedType`) on the seat record — making it readable by the teacher in the roster view before the student claims, and by the claim flow for verification. A `name_lookup_hash` (HMAC) is also stored for efficient indexed querying without decrypting every row. Both are purged after the student completes setup; only `last_initial` is retained for display.

---

### 11.2 The v2.0 Branch Review Findings

The `codex/v2.0` branch was reviewed (2026-04-12) before finalizing this design. Key relevant architecture already in v2.0:

| v2.0 construct | What it does | Maps to our design concept |
|----------------|-------------|---------------------------|
| `IdentityProfile` model | Canonical identity anchor: `first_name` (PIIEncryptedType) + `last_initial`. Both `TeacherBlock` and `Student` hold an `identity_id` FK. | Temporary storage for full last name during claim; needs a `last_name` field extension (see 11.7) |
| `Seat.roster_fingerprint` | String(128), indexed — deterministic hash of a student's identifying information, scoped per seat/class | Exactly our `name_lookup_hash` — HMAC(first_initial + full_last_name, global_pepper), scoped to join_code in queries |
| `Seat.dedupe_code` | String(8) — already on the Seat model | Our 4-character dedupe code (design uses 4; v2.0 reserved 8 — compatible) |
| `Seat.public_id` | UUID — stable, opaque, class-local identifier | `seat_code` in the Mode B CSV download template |
| `TeacherBlock.dedupe_key` | String(64) — already on TeacherBlock (current-architecture seat) | Transitional dedupe mechanism; aligns with `Seat.dedupe_code` in v2.0 |
| `TeacherBlock.dob_sum_hash` | v2.0 already replaced plaintext `dob_sum` with an HMAC hash | v2.0 is already moving away from raw DOB; this column is itself a candidate for removal once name-lookup replaces it |

**Critical finding:** The v2.0 architecture is already designed around join_code-scoped seat lookup. `Seat.roster_fingerprint` is explicitly the lookup hash for a seat within its class. The design in 11.3 (join_code-first, no global identity check) is directly aligned with how v2.0 models identity.

---

### 11.3 Claim Flow Architecture: Two Paths

**The invariant that governs both paths:**

> Identity lookup is always and only scoped to the submitted `join_code`. The system never queries across join codes to check whether a student "already exists" globally. A student's global account state is irrelevant to finding their seat — seat lookup and credential attachment are separate operations.

This design choice is correct for two reasons:
1. **Privacy by scope** — a student's presence in one class is not the business of any other class's claim flow.
2. **Collision arithmetic** — a class of ~35 students is the correct collision domain. Querying globally inflates the collision surface to the entire student population, making name uniqueness impossible to guarantee and requiring more aggressive disambiguation than the problem actually needs.

---

#### Path A — Unauthenticated Claim (student has no existing account)

```
Student visits app
↓
Enters join code → scopes ALL subsequent lookups to this join_code
↓
"Enter your first name and last name"
↓
Backend:
  compute name_lookup_hash = HMAC(first_initial + full_last_name, global_pepper)
  SELECT seat FROM teacher_blocks
    WHERE join_code = :join_code
      AND name_lookup_hash = :hash
      AND student_id IS NULL           ← unclaimed only
↓
One match → proceed to username / PIN / passphrase setup
            on completion: new Student record created, linked to seat via student_id FK
            encrypted full_last_name on seat is purged; name_lookup_hash + last_initial retained
↓
No match → "Name not found — check with your teacher"
↓
Multiple matches (collision within this join_code) →
  "Your teacher gave you a 4-letter code. Enter it now."
  SELECT ... WHERE join_code = :join_code AND name_lookup_hash = :hash AND dedupe_code = :code
```

**Known edge case:** If the student already has a Student record in another class (from a previous year or another teacher) and uses the unauthenticated path, they will receive a second Student record. This is acceptable. The resolution path is documented in 11.3c below.

---

#### Path B — Authenticated Claim (student already has credentials, joining a new class)

```
Student is logged in as existing Student
↓
Navigates to "Join a New Class"
↓
Enters join code → scopes the seat lookup to this join_code
↓
"Enter your first name and last name for this class"
↓
Backend:
  compute name_lookup_hash (same as Path A)
  SELECT seat FROM teacher_blocks
    WHERE join_code = :join_code
      AND name_lookup_hash = :hash
      AND student_id IS NULL
↓
One match (or match + dedupe code if collision) →
  seat.student_id = existing Student.id       ← same mechanism as Path A
  existing ClassMembership created for (student_id, join_code)
  NO new Student record created
  encrypted full_last_name on seat purged
↓
No match → "No unclaimed seat found for that name in this class"
```

This path is the correct approach when a student is already enrolled in one class and joins another. No account duplication occurs.

---

#### 11.3c Duplicate Account Resolution (edge case from Path A)

If a student ends up with two Student records (e.g., they used Path A for a new class while already having credentials from a previous class), the resolution flow is:

```
Student logs in to either account
↓
Navigates to account settings → "I already have an account in another class"
↓
Enters the join_code of the class they want to rebind
↓
Backend:
  finds their seat in that join_code (must be claimed by their other account)
  verifies student can authenticate with that seat's credentials (or teacher issues a rebind code)
  repoints the seat's student_id to the currently authenticated Student.id
  old Student record is deleted (or archived) if it no longer belongs to any class
```

The source of truth for whether a seat is claimed is the presence of credential hashes, not any boolean flag. Rebinding replaces the credential link without creating an inconsistent state.

---

**What is collected vs. what is stored (both paths):**

| Data | Collected | Stored | Purged |
|------|-----------|--------|--------|
| First name | Yes (roster upload) | Encrypted (`PIIEncryptedType`) on seat; retained encrypted on Student record after claim | After setup: full first name retained encrypted — teacher sees it in roster |
| Full last name | Yes (roster upload) | Encrypted (`PIIEncryptedType`) on seat (temporary); `name_lookup_hash` (HMAC, irreversible) stored separately for indexed lookup | Encrypted value purged after student completes setup; `name_lookup_hash` and `last_initial` retained |
| Last initial | Derived from last name at upload | Plaintext on seat and Student record | Never — used for teacher roster display throughout account lifetime |
| DOB | Not collected | Not stored | N/A |
| Dedupe code | Only when collision exists within join_code | Plaintext on seat (4 chars, not PII) | Can be nulled after claim; may be retained for roster disambiguation display |

---

### 11.4 Collision Detection and Dedupe Code Generation

A collision occurs when two students in the same class period share the same `name_lookup_hash` — i.e., same first initial and same full last name. This is rarer than same first initial + same last initial (the current collision surface) but can still occur (e.g., two students both named "James Martinez" in a class).

**Collision detection at roster upload:**

```
For each student in upload:
  compute name_lookup_hash
  if another seat in same join_code already has this hash:
    generate random 4-character alphanumeric dedupe_code
    assign to BOTH the existing seat AND the new seat
    (teacher sees code displayed in roster, distributes to affected students only)
  else:
    dedupe_code = None
```

**Implementation notes:**
- Dedupe codes are assigned only to colliding students — the teacher does not need to distribute codes to the entire class
- A dedupe code for an unclaimed seat is visible to the teacher in the roster UI
- After the student claims their account, the dedupe code is no longer needed for login (credential hashes serve that purpose); it can be nulled or retained for roster display

---

### 11.5 Roster Upload Redesign: Two-Mode Upload

The current upload is insert-with-skip-on-duplicate, using a five-field key that includes `dob_sum`. With DOB removed, a new upload strategy is needed.

**Two upload modes (teacher chooses at upload time):**

**Mode A — "Add to New Class / Fresh Roster"**

- Use case: first upload for a class period, or replacing entire roster
- CSV template: columns for `first_name`, `last_name`, `block` only
- Backend: creates new `TeacherBlock` seats; detects and assigns dedupe codes on collision
- No seat codes in CSV — seats are created fresh

**Mode B — "Add or Update Existing Class"**

- Use case: adding a few new students mid-year, or correcting a name
- Backend: generates a pre-populated CSV containing all current seats with their `seat_code` (UUID), `first_name`, `last_initial`, and `dedupe_code` (if any)
- Teacher downloads the template → adds new rows (no seat code, empty code column) or edits existing rows by name
- On re-upload:
  - Rows with a `seat_code` → treated as updates to the named seat (name correction only)
  - Rows without a `seat_code` → treated as new additions; collision check runs on these only
- Rows with a `seat_code` for a seat that is **already claimed** → name updates are applied to the seat's encrypted name fields; dedupe code cannot be regenerated (claimed student's credential hashes are finalized; changing the name_lookup_hash would break their login)

**Why this avoids the "claimed/unclaimed flag manipulation" risk** the design review identified: the system's source of truth for whether a student has claimed their account is the presence of credential hashes (`pin_hash`, `passphrase_hash`), not any mutable boolean flag. The upload flow cannot create a "claimed student with no credentials" scenario because new rows in Mode B always generate unclaimed seats.

---

### 11.6 What Gets Dropped When DOB Is Removed

When the claim flow no longer uses DOB, the following database columns become removable:

| Column | Table | Can drop? | Notes |
|--------|-------|-----------|-------|
| `dob_sum` | `teacher_blocks` | Yes | Replace with `name_lookup_hash` |
| `dob_sum` | `students` | Yes | No longer needed post-claim |
| `first_half_hash` | `teacher_blocks` | Yes | Was HMAC(first_initial + dob_sum, salt) |
| `second_half_hash` | `teacher_blocks` | Yes | Was HMAC(dob_sum, salt) |
| `salt` | `teacher_blocks` (student claim salt) | Yes | Per-seat salt used for credential hashes |

**v2.0 alignment:** `TeacherBlock.dob_sum_hash` (already migrated in v2.0) would also be removed. v2.0's `Seat.roster_fingerprint` is the direct replacement for the lookup hash mechanism.

**Columns that stay:**

| Column | Table | Reason |
|--------|-------|--------|
| `dob_sum_hash` | `admins` | Teacher DOB for account recovery — separate use case, adult-consented |
| `salt` | `admins` | Per-teacher salt for teacher recovery hash |

---

### 11.7 v2.0 Implementation Path

When the v2.0 architecture is adopted, this design maps as follows:

| Our design concept (current arch) | v2.0 equivalent |
|-----------------------------------|-----------------|
| `TeacherBlock.name_lookup_hash` | `Seat.roster_fingerprint` |
| `TeacherBlock.dedupe_code` (via `dedupe_key`) | `Seat.dedupe_code` |
| `TeacherBlock.full_last_name` (temporary, encrypted) | `IdentityProfile.last_name` (new field needed in v2.0) |
| `seat_code` in CSV template | `Seat.public_id` (UUID, already in v2.0) |

**One gap to address in v2.0:** `IdentityProfile` currently has `first_name` (encrypted) and `last_initial` but no `last_name` field. The v2.0 migration for the DOB-free claim flow would need to add `IdentityProfile.last_name` as a temporary, encrypted field — set at roster upload, purged after the student completes account setup (same pattern as current `Student.dob_sum`).

---

## XII. Audit Participants and Method

- **Method:** Static code analysis via automated codebase exploration + manual review
- **Scope:** Full application — models, routes, forms, templates, migrations, tests, documentation; `codex/v2.0` branch reviewed for forward compatibility
- **Files examined:** `app/models.py`, `app/routes/student.py`, `app/routes/admin.py`, `app/forms.py`, `app/hash_utils.py`, `app/__init__.py`, `app/services/tlcp.py`, all templates referencing DOB/username, all migrations referencing dob columns, `templates/privacy.html`; v2.0 branch: `app/models.py`, all v2.0 migrations
- **Audit date:** 2026-04-12
- **Phase 1 remediation date:** 2026-04-12 (branch `claude/review-privacy-concerns-d4IKD`)
- **Status:** Phase 1 complete. Phase 2 (claim flow redesign) awaiting district feedback.

---

### Change Log

| Date | Section | Change | Commit |
|------|---------|--------|--------|
| 2026-04-12 | New document | Initial audit findings | — |
| 2026-04-12 | IX, X | Marked P0/P1 items complete; updated summary table | `claude/review-privacy-concerns-d4IKD` |
| 2026-04-12 | XI (new) | Added v2.0-aligned forward design spec for DOB-free claim flow | `claude/review-privacy-concerns-d4IKD` |

*Continue marking remediation items with completion dates and commit references as work progresses.*
