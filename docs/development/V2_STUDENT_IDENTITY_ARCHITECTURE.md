# Classroom Token Hub (CTH) v2.0 Identity Architecture

## Core Design Principle

Identity in CTH is separated into three distinct layers:

- **User** → authentication identity
- **Seat** → participant in a class universe
- **Class** → economic universe container

Economic activity is always tied to **seat\_id**, never directly to a user.

---

# Identity Layers

## Users (Credential Identity)

Purpose: authentication, recovery, and global security state.

Typical fields:

- id (PK)
- public\_id
- username\_hash
- username\_lookup\_hash
- pin\_hash
- passphrase\_hash
- reset\_code\_hash (cleared after successful recovery)
- reset\_code\_expires\_at (stored in UTC; displayed as local time or default PST/PDT; cleared after recovery)
- money\_action\_cooldown\_until


- has\_completed\_setup
- created\_at
- updated\_at

Rules:

- Users represent login credentials.
- Users may own **multiple seats**.
- Users with no seats may be garbage collected.

---

## Classes (Universe Container)

Purpose: define an isolated classroom economy universe.

Fields:

- id (PK)
- public\_id
- join\_code\_token
- display\_name
- created\_at
- updated\_at

Rules:

- If the row exists, the universe exists.
- No archive or inactive states.
- Deleting a class deletes all seats and class-scoped economic state.

---

## Seats (Class-Local Actor)

Purpose: represent a participant within a class universe.

Fields:

- id (PK)
- public\_id
- class\_id (FK)
- user\_id (FK, nullable until claimed)
- role (teacher | student)
- block\_identifier
- roster\_fingerprint
- dedupe\_code (nullable)
- claimed\_at
- created\_at
- updated\_at

Rules:

- A seat belongs to exactly one class.
- A user may own multiple seats.
- Seats represent **actual actors** inside the universe.

Recommended constraints:

- UNIQUE(class\_id, roster\_fingerprint, dedupe\_code)
- UNIQUE(user_id, class_id)

---

## Identity Profiles (Display Identity)

Purpose: store human-facing identity with minimal PII.

Fields:

- id (PK)
- seat\_id (FK, UNIQUE)
- first\_name\_encrypted
- last\_initial
- created\_at
- updated\_at

Rules:

- One profile per seat.
- Profiles contain only display identity.

---

# Claim and Roster Identity

## Where claim identity lives

Claim identity should live directly on **seats**, not in a separate `claim_identity` or `roster_entries` table.

Reasoning:

- Roster upload already creates the participant record.
- There is no separate enrollment staging workflow in CTH.
- Historical enrollment tracking is intentionally not preserved.
- Editing pending roster rows can be handled by deleting and re-adding seats.
- A separate claim table would introduce a second object that always moves with the seat and would add complexity without solving a real problem.

So the seat remains both:

- the roster-created pending participant
- the eventual claimed actor in the universe

This keeps the model aligned with the core invariant:

**If the seat exists, the participant exists in that class universe.**

## Recommended seat claim fields

Claim-related data stored on `seats`:

- `roster_fingerprint`
- `dedupe_code` (nullable)
- `claimed_at` (nullable)
- `user_id` (nullable until claimed)

Optional implementation detail:

- `dedupe_code` may be stored encrypted if desired for consistency, but it does not need to be part of the fingerprint itself.

## Recommended indexes and constraints

Primary integrity constraint:

- `UNIQUE(class_id, roster_fingerprint, dedupe_code)`

Recommended lookup indexes:

- index on `(class_id, roster_fingerprint)` for claim lookup
- index on `(user_id)` for loading a user's universes
- index on `(class_id, role)` for roster/admin views
- optional index on `(class_id, claimed_at)` if pending vs claimed seat queries become common

Lookup behavior:

1. Student enters join code, first initial, last name, DOB, and optional dedupe code.
2. Backend resolves `class_id` from join code.
3. Backend computes `roster_fingerprint`.
4. Backend queries by `(class_id, roster_fingerprint)`.
5. If exactly one seat matches, claim proceeds.
6. If multiple seats match, dedupe code is required.

This keeps lookup performance logarithmic and keeps all claim identity data attached to the actor itself.

## Why no separate claim bundle table

A separate table would only be justified if CTH supported things it intentionally rejects, such as:

- pre-seat roster staging
- SIS synchronization workflows
- historical enrollment archives
- multi-stage enrollment approval

Since those are unnecessary or forbidden in CTH, claim identity should remain seat-local.

---

# Claim and Roster Identity

Roster uploads create **seats** directly.

Teacher provides:

- first name
- last name
- date of birth
- block/period

Backend creates:

- seat
- identity\_profile
- roster\_fingerprint

## Roster Fingerprint

Fingerprint derived from minimal identity fields.

Example concept:

HMAC(server\_secret, normalized\_first\_name | normalized\_last\_name | dob\_iso)

This value is stored as `roster_fingerprint`.

Database constraint ensures uniqueness within class scope.

---

# Duplicate-on-Paper-Only Handling (DOPO)

Rare case: two students share the same name and DOB within a class.

System behavior:

1. Generate a two-digit `dedupe_code` (00–99).
2. Store it on the seat.
3. Teacher communicates code to affected students.

Claim flow:

Student enters:

- join code
- first initial
- last name
- date of birth
- optional deduplication code

Backend:

1. Compute roster\_fingerprint.
2. Search for seats matching class\_id + fingerprint.

Cases:

- Single match → claim proceeds.
- Multiple matches → require dedupe\_code.

---

# Economic State

All economic activity attaches to **seat\_id**.

Examples:

- ledger\_entries
- payroll\_events
- hall\_pass\_logs
- store\_purchases

Optional denormalization may include class\_id for indexing.

---

# Recovery Model

Recovery targets **users**, not seats.

Reason:

Credentials may own multiple seats across classes.

Flow:

1. Teacher initiates recovery.
2. Backend identifies seat.
3. Seat resolves to user.
4. Recovery code stored on users.
5. Student resets credential.

Security:

`money_action_cooldown_until` enforces global throttle across all seats owned by the credential.

---

# Teacher Identity Modes

## Teacher Credential

Admin user identity.

Owns teacher seats in classes.

## Teacher-as-Student

Same credential owning two seats in a class:

- teacher seat
- student seat

Permissions determined by active seat context.

## Teacher Shadow (Optional)

Separate credential used to experience the system as a student.

Not required for core v2.

If implemented later, shadow status should live on `users`.

---

# Deletion Semantics

Delete seat:

- removes participant from that class universe

Delete class:

- removes entire universe

Delete last seat for a user:

- user becomes eligible for garbage collection

Re-adding later creates a new seat with new identity in that universe.

---

# Core Invariants

1. Users represent authentication identities.
2. Classes represent universes.
3. Seats represent actors inside universes.
4. Economic activity belongs to seat\_id.
5. Credential recovery belongs to users.
6. Role is seat-scoped, not user-scoped.
7. Existence of rows defines reality.

