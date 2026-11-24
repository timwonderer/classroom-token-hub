# FEAT-IDEN-009: Identity Session Lifecycle

| Reference Number | Version | Effective Date | Supersedes | Authority Level | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FEAT-IDEN-009 | 1.0 | 2026-11-24 | — | Normative | ACTIVE |

---

## I. Purpose

This FEAT is the sole lawful mutation path for establishing, re-pointing and revoking a
sign-in, for all three roles (student, teacher, sysadmin). It owns every write to the
session-identity fields on `users`: `current_session_nonce`, `current_session_started_at`,
`current_session_expires_at`, `last_active_class_id`, `last_active_seat_id`. One exception:
`select_student_class_fields` is also callable under `FEAT-IDEN-005` (Authenticated Class
Binding), for the pointer move that is the last step of binding a newly-added class — see
§II.1.

**Why this is its own FEAT, not FEAT-IDEN-001.** FEAT-IDEN-001 (Unauthenticated Student Seat
Claim) is read-only (§IV.1 of that contract) and its precondition is the *absence* of an
authenticated principal (§II.0, DOM-IDEN-005 §VII). Every operation this FEAT covers writes to
`users`, and most of them (teacher/sysadmin class selection, sign-out) run only when a principal
is already authenticated — the exact state FEAT-IDEN-001 refuses to run under. Prior to this
FEAT, every call site in `app/routes/admin.py`, `app/routes/student.py`, `app/routes/system_admin.py`
and `app/auth.py` ran this mutation inside `FEATContext("FEAT-IDEN-001", ...)` (or, for two sysadmin
and one teacher passkey route, `FEAT-OPS-001` — "Maintenance/Cleanup Operations" — an unrelated FEAT
that happened to satisfy the commit-boundary enforcement without describing what was actually
happening) (#1777).

**Why one contract covers establishment, class selection and revocation together**, rather than
splitting revocation onto its own FEAT as #1776 did provisionally: they are one lifecycle over the
same row fields. A sign-in is established, is possibly re-pointed at a different already-bound
class, and is eventually revoked; splitting the lifecycle across contracts each covering a subset
of the same fields invites exactly the drift this FEAT closes (§X, Version 1.0 Amendment).

**Governing Authority:**
- INV-ARC-006 §V and §VII (all state mutation inside explicit domain commands; FEAT composes
  domain commands, never mutates `users` directly)
- DOM-IDEN-002 §Session Establishment, DOM-IDEN-003 §Session Establishment (the per-role session
  shape: student/teacher fixed-window fields, sysadmin idle-only; the fixed 60-minute teacher
  window that activity never extends)
- DOM-IDEN-006 §VIII, §IX (canonical context resolution; sign-out is not class-scoped)
- FEAT-CORE-000 (Feature Execution Constitutional Directive)

---

## II. Execution Context

### 0. Operation Kinds

This FEAT covers four distinct operations, dispatched by the calling route (there is no single
shared request shape — unlike FEAT-IDEN-001, several of these run only for an *already*
authenticated principal):

| Operation | Precondition | Fields written |
|---|---|---|
| **Establish** (sign-in) | No valid existing session for this login attempt (credentials just verified) | nonce, `started_at`/`expires_at` (student/teacher only), optionally `last_active_class_id`/`seat_id` |
| **Select class** | An authenticated principal already holds a session | `last_active_class_id`, `last_active_seat_id` only — nonce is NOT rotated |
| **Revoke** (sign-out) | A session cookie naming a `user_id` and a `current_session_nonce` | clears nonce and, for roles that use one, `expires_at` |
| **CLI bootstrap** (sysadmin only) | Operator CLI invocation, no browser session involved | — (verified: `create-sysadmin` does not write any session-identity field; see Amendments) |

### 1. Identity-Domain Commands (MANDATORY entry points)

Routes, `app/auth.py` and the CLI delegate exclusively to `app/services/identity_service.py`:

- `establish_teacher_session_fields(user, *, started_at, expires_at)` — fixed 60-minute window
  (DOM-IDEN-003), fresh nonce.
- `establish_student_session_fields(user, *, started_at, expires_at, class_id=None, seat_id=None)`
  — fixed window, fresh nonce; `class_id`/`seat_id` omitted when login has no valid persisted
  class selection (the session is established class-less, pending `select_class_context`).
- `establish_sysadmin_session_fields(user)` — fresh nonce only. Sysadmin has no DB-stored expiry;
  its window is idle-based and tracked in the signed cookie
  (`app.auth.SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES`), never on the row.
- `select_student_class_fields(user, *, class_id, seat_id)` / `select_teacher_class_fields(user, *,
  class_id, seat_id)` — move the canonical active-class pointers on an already-authenticated
  principal. Both pointers move together (a lone `last_active_class_id` update leaves the seat
  pointing at the old class, which the context resolver rejects as `ContextMismatch`).
- `revoke_signed_in_session(user_id, nonce)` — locked (`FOR UPDATE`), nonce-conditional. Returns
  `False` without writing anything when the nonce no longer matches (a stale/replayed revoke must
  not end a newer sign-in elsewhere).

Each command raises `PermissionError` unless `FEAT-IDEN-009` is the active FEAT
(`get_active_feat_name()`), the same guard shape `create_system_principal` (FEAT-IDEN-008) already
uses — except `select_student_class_fields`, whose guard also accepts `FEAT-IDEN-005` (§I).

`app/auth.py`'s `establish_teacher_session` / `establish_student_session` /
`establish_sysadmin_session` are the FEAT-external callers' entry points: they compute the
clock-dependent values (via `canonical_temporal_resolver`, SPEC-TIME-001), call the
identity-domain command for the row write, and set the matching non-persisted Flask `session`
dict keys. **They do not themselves open the FEAT context** — the caller (a route) does, because
the correlation/idempotency key is request-shaped, not something `app/auth.py` can manufacture
for every caller uniformly. `end_signed_in_session` is the one exception: it opens
`FEAT-IDEN-009` itself (keyed by the `user_id`/nonce being revoked, which it already has from the
session), so a caller must **not** wrap it in another FEAT context.

### 2. Call Sites (all retargeted from FEAT-IDEN-001 / FEAT-OPS-001 by this FEAT, #1777)

- `app/routes/admin.py`: teacher TOTP login, teacher passkey login (`passkey_auth_finish`,
  previously `FEAT-OPS-001`), `_apply_teacher_class_selection`, `set_current_class` (AJAX class
  switch).
- `app/routes/student.py`: `_complete_student_login` (covers both the direct-dashboard and
  class-selector branches of sign-in), `select_class_context`'s POST handler (previously
  `FEAT-IDEN-005`, which is Authenticated Class Binding — a different operation that happens to
  share the same `switch_student_session_context` helper), `switch_class`.
- `app/routes/system_admin.py`: `_complete_sysadmin_login` (previously `FEAT-OPS-001`),
  `passkey_auth_finish` (previously `FEAT-OPS-001`).
- `app/auth.py`: `end_signed_in_session`, shared by all three roles' logout routes.

---

## III. Orchestration Logic

### A. Establish

1. Authenticate the principal (TOTP, passphrase, or passkey — owned by the calling route, not
   this FEAT).
2. Compute `started_at` (now) and, for student/teacher, `expires_at` (fixed window: see DOM-IDEN-002
   §Session Establishment for the student window, DOM-IDEN-003 §Session Establishment for the
   teacher window) via `canonical_temporal_resolver`.
3. Call the role's `establish_*_session_fields` command. It replaces all three session fields
   unconditionally (DOM-IDEN-003 §Session Establishment: "All three session fields are replaced
   on the next successful sign-in") — a prior sign-in's nonce is simply overwritten, not checked.
4. Write the matching Flask `session` keys, including the cookie-side expiry mirror
   (`SESSION_EXPIRES_AT_KEY`) so the cookie does not outlive the server-side window.

### B. Select Class

1. Precondition: an authenticated principal (a resolved `CanonicalContext`, or for the
   student/teacher class-selector gates, a session `user_id` read via `get_current_user()`).
2. Resolve and validate the target `Seat` for the requested `class_id` under the caller's own
   authority checks (teacher ownership, student seat binding) — this FEAT does not re-derive
   authorization, only performs the write once the route has established it.
3. Call `select_student_class_fields` / `select_teacher_class_fields`. The nonce is **not**
   rotated — this is the same sign-in, re-pointed at a different class.

### C. Revoke

1. Read `user_id` and `current_session_nonce` from the Flask session. If either is absent,
   there is nothing to void on the row (a session that was never fully established, or already
   cleared) — go straight to clearing the cookie.
2. Call `revoke_signed_in_session(user_id, nonce)` under a row lock. It clears the nonce (and,
   where present, `expires_at`) only if the row's current nonce still matches — a stale or
   replayed revoke must not end a newer sign-in that has since replaced the nonce.
3. Clear the Flask session unconditionally, regardless of whether the row write took effect.

Per DOM-IDEN-006 §IX, revocation is not class-scoped: a student with no active class can still
sign out.

---

## IV. Invariants & Constraints

### 1. Explicit Domain Commands Only (MANDATORY)
No route, no `app/auth.py` function, and no CLI command writes `current_session_nonce`,
`current_session_started_at`, `current_session_expires_at`, `last_active_class_id`, or
`last_active_seat_id` directly. Every such write goes through one of the commands in §II.1
(INV-ARC-006 §V, §VII).

### 2. Fixed Window, Never Extended by Activity (MANDATORY)
`current_session_expires_at` is set once, at establishment, and is never recomputed by request
activity for the role it governs a fixed window for (teacher: DOM-IDEN-003; student: DOM-IDEN-002).
Re-pointing the active class (§III.B) never touches it. Only a fresh `establish_*` call replaces
it.

### 3. Nonce-Conditional, Locked Revocation (MANDATORY)
Revocation never clears a session's row state without first confirming, under `FOR UPDATE`, that
the nonce it was asked to void is still the row's current nonce. A copy of an old cookie, or a
revoke request that races a newer sign-in, must leave the newer sign-in intact.

### 4. Sysadmin Carries No Fixed-Window Expiry (MANDATORY)
`establish_sysadmin_session_fields` never writes `current_session_expires_at`. Sysadmin idle
timeout (`SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES`) is enforced from the signed cookie's
`last_activity`, per the existing `_system_admin_timeout_expired` check in `app/auth.py` — this
FEAT does not change that mechanism, only where the nonce write happens.

### 5. No Inter-Role Inheritance (MANDATORY)
Establishing a new sign-in clears the Flask session first (`session.clear()`), so a new principal
inherits nothing from whatever was there before — not a teacher's expiry key, not a stale class
id, not a leftover nonce.

---

## V. Idempotency

Per FEAT-CORE-000 §III.3, every call site supplies or accepts a generated `idempotency_key`
(`key_per_call=True` on the decorated routes). A replayed *establish* call simply re-establishes
the session with a fresh nonce — establishment has no stored reservation to replay, by design
(DOM-IDEN-003 §Session Establishment: fields are unconditionally replaced). A replayed *revoke*
call is naturally idempotent: `revoke_signed_in_session` is a no-op once the nonce it names no
longer matches the row (already voided by the first call, or superseded by a newer sign-in).

---

## VI. Audit Requirements

Session establishment and revocation are already logged structurally: `FEAT-ENTRY`/commit-ownership
logging from `FEATContext` itself (FEAT-CORE-000), plus the existing
`SESSION-CONTEXT-SWITCH` log line emitted by `switch_student_session_context` for class
re-pointing. No PII (names, emails) is logged by any of these paths; only ids and class
references (`class_log_ref`).

---

## VII. Failure Scenarios

| Scenario | Behavior |
|---|---|
| Stale cookie's nonce no longer matches the row | `revoke_signed_in_session` returns `False`, writes nothing; the Flask session is still cleared locally |
| Class-selection target seat does not resolve / fails authority check | Refused by the calling route before this FEAT's command is invoked; no partial write |
| `select_*_class_fields` called with an unauthenticated principal | Not reachable through the declared call sites (§II.0 precondition); any new call site must resolve a principal first |
| Establishment called twice in rapid succession for the same login (e.g. a double-submitted form) | Each call independently writes a fresh nonce; the second write simply supersedes the first — this is establishment's defined "replace unconditionally" behavior (DOM-IDEN-003 §Session Establishment), not a conflict |

---

## VIII. Dependencies

- `docs/INVARIANT/ARCHITECTURE/INV-ARC-006_EXPLICIT_MUTATION_ONLY.md`
- `docs/DOMAIN/DOM-IDEN-002_STUDENT_IDENTITY_ARCHITECTURE.md`
- `docs/DOMAIN/DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md`
- `docs/DOMAIN/DOM-IDEN-006_CANONICAL_CONTEXT_RESOLUTION.md`
- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/FEATURE-EXECUTION/FEAT-IDEN-001_UNAUTHENTICATED_STUDENT_SEAT_CLAIM_REMEDIATED.md` (the
  contract this FEAT's call sites were incorrectly running under)

---

## IX. Implementation Checklist

Before code review, verify:

- [ ] No route, `app/auth.py` function or CLI command sets `current_session_nonce`,
      `current_session_started_at`, `current_session_expires_at`, `last_active_class_id` or
      `last_active_seat_id` directly — only through §II.1's commands
- [ ] Every declared call site (§II.2) opens `FEATContext("FEAT-IDEN-009", ...)`, not
      `FEAT-IDEN-001` or `FEAT-OPS-001`
- [ ] `select_*_class_fields` never rotates the nonce
- [ ] `revoke_signed_in_session` is locked (`FOR UPDATE`) and nonce-conditional
- [ ] The teacher fixed 60-minute window is never recomputed outside `establish_teacher_session_fields`
- [ ] Sysadmin establishment never writes `current_session_expires_at`
- [ ] The #1776 replay and stale-cookie regression tests
      (`tests/dom/identity/test_sign_out_and_teacher_session_window.py`) still pass unmodified in
      behavior

---

## X. Amendments

Revisions to this document SHALL:
1. Increment the version.
2. Update the effective date.
3. Stay consistent with INV-ARC-006, DOM-IDEN-002 and DOM-IDEN-003's Session Establishment
   sections.

**Version 1.0 (2026-11-24), submitted for owner review (#1777):** New contract. Supersedes
FEAT-IDEN-001 and FEAT-OPS-001 as the mutation path for every identity-session call site named in
§II.2. During implementation, verified against current code (not assumed from the issue text)
that:
- `app/cli_commands.py`'s `create-sysadmin` does **not** write any session-identity field — it
  delegates to `provision_sysadmin` (FEAT-IDEN-008), which creates the `User` row only. The issue
  text's inclusion of this call site among the violators did not check out against the code as it
  stands; no change was made there.
- Two sysadmin routes (`_complete_sysadmin_login`, sysadmin `passkey_auth_finish`) and one teacher
  route (`passkey_auth_finish`) were running this mutation under `FEAT-OPS-001`
  ("Maintenance/Cleanup Operations"), not `FEAT-IDEN-001` — a second, independent mismatch the
  issue's own FEAT-IDEN-001 grep would not have caught. Included in this FEAT's scope for the same
  reason as the FEAT-IDEN-001 call sites: none of these three routes performs maintenance or
  cleanup.
- `student.select_class_context`'s POST handler and `admin.set_current_class` were also, for the
  same reason, retargeted here rather than left on `FEAT-IDEN-001`/`FEAT-IDEN-005` — they are the
  same "select class" operation as `_apply_teacher_class_selection`/`switch_class`, just reached
  from a different entry point.

**Post-approval cleanup (2026-11-24):** two remaining direct writes to `users.last_active_class_id`/
`last_active_seat_id` were found by review and closed before merge: `student._complete_student_login`'s
invalid-persisted-class repair (now `identity_service.clear_student_class_fields`, a new command
added for this exact repair) and `admin.login`'s automatic single-class teacher selection (now
`select_teacher_class_fields`, already in use on the explicit-selection paths). §I and §II.1 were
also corrected to document the `FEAT-IDEN-005` exception on `select_student_class_fields`'s guard,
and that `end_signed_in_session` opens its own `FEAT-IDEN-009` context rather than requiring one
from its caller.

**Promoted to ACTIVE (2026-11-24):** the owner reviewed and approved this contract's shape
(operation grouping, and the FEAT-IDEN-001/FEAT-IDEN-005 reassignments in particular) prior to
merge.
