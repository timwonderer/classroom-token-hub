# SPEC-IDEN-001: Username Retention Verification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-IDEN-001 | 1.2 | 2026-09-29 | 1.1 | Technical Specification |

## I. Purpose

Student setup must verify that the student can retrieve their saved username.
An acknowledgment, countdown or repeated button press cannot satisfy this gate.
This implements the supplied build specification proposed as
`SPEC-AUTH-USERNAME-RETENTION`, under the canonical Identity namespace.

## II. Scope and authority

Applies to initial student claim and student recovery credential setup.
Incorporated by FEAT-IDEN-002 §III.A, subordinate to INV-CORE-000 §III.2/III.7,
INV-ARC-005/007/018/020, DOM-IDEN-002 and incorporated SPEC-SEC-001 §V.2/V.5.
Generation entropy, vocabulary, format, collision handling, normal login and
teacher/sysadmin access do not change. No username-history or retrieval feature
is authorized.

## III. Interaction

### Presentation

Show the generated username prominently, with **Copy username** and:

> Save your username
>
> You will need this username when you sign in.
>
> Save it somewhere you can access later. Classroom Token Hub does not keep a
> readable copy of your username, so your teacher cannot look it up for you if
> you forget it.

Remove the acknowledgment checkbox. PIN/passphrase fields stay disabled until
verification succeeds. **I've saved my username** opens verification with an
empty, labeled input. While verification is open, the generated username must
not appear anywhere on that surface or in helper text/attributes. Copying from
presentation remains allowed.

### Retrieval

> Enter your saved username
>
> Type the username you just saved. This makes sure you'll be able to find it the
> next time you sign in.

The server compares canonical username HMAC lookup digests in constant time.
Canonical matching is NFKC plus trim, case-sensitive. JavaScript never decides a
match. A mismatch keeps the username hidden, prevents progression, and announces:

> That doesn't match your username. Check the copy you saved and try again.

There is no attempt-count bypass. **Show my username again** returns to
presentation with the same username. Escape has the same behavior. Reopening
verification clears the input. A match enables credentials and focuses the PIN.
A separate verification page supplies the same server check when the modal
cannot run; its successful POST renders the credential form with the same page
token and an explicit action targeting credential setup.

### Paste and accessibility

Ordinary paste/drop and corresponding `beforeinput` insertion events are blocked
only on the retention input. Login, recovery and all other credential inputs
retain paste and password-manager support. Typing, dictation and IME remain
available. **Can't type in this box?** offers an explicit assistive-input
accommodation to allow paste from the student's saved copy. This accommodation
still requires the same server match and page-bound proof; it is not an
acknowledgment bypass. Only a non-PII accommodation flag may be logged.

Use programmatic labels, live announcements and visible keyboard focus. Opening
verification focuses its input; mismatches focus the error; revealing restores
focus to the opener. No timer or color-only state is permitted. Both presentation
and verification require rendered mobile/desktop accessibility validation.

## IV. Volatile setup state

INV-ARC-018 §IX permits a dedicated memory-only Redis service shared across app
workers. The browser stores only a random 256-bit `student_setup_token`. Its hash
addresses the record; it is never placed in a URL. The record contains an opaque
scope binding, owner reference for deletion, random generation id, Fernet-encrypted
username, attempt count, page proof and completion/collision state. It is not a
User or Seat, creates no schema field, and grants no identity authority.

A successful claim or recovery acceptance creates a new attempt. Creation locks
and rechecks the owning Seat/class or recovery User against deletion/revocation.
Every subsequent request independently validates the existing identity contract:
initial claim requires the current unclaimed Seat generation; recovery requires
only the User and its unexpired, server-validated nonce. Recovery must not resolve
participation. Scope mismatch or missing/replaced state fails closed.

The fixed TTL is at most 30 minutes and, for recovery, at most the remaining
recovery deadline. Reading, verifying, retries and collisions never extend it.
GET renders only; it does not create, regenerate, verify or refresh state.

Source-word submission calls the existing generator once. Repeated submission,
refresh, back/forward, show/hide and mismatch do not change the result. Only a
new setup session or explicit source-word replacement after the existing
collision refusal may generate a replacement. Concurrent generation uses a
compare-and-set transaction so only one result survives.

The application checks that RDB/AOF and slow logging are disabled, the store is a
primary with no replicas, and no snapshot is in progress. The supplied service
ACL prohibits persistence/configuration mutation, replication and command capture.
The service runs without swap/core dumps and writes only to its memory-backed
runtime directory. No backup or host snapshot may capture it. See
`infra/student-setup/README.md` for the required provisioning evidence.

An absent, full, unsafe or unavailable store produces a generic 503; loss or
expiry of an attempt requires restarting setup. There is no database, cookie or
worker-local fallback. Storage loss never changes existing account credentials.

## V. Proof, completion and lifecycle

Every rendered setup page has a fresh random page token. A successful match
records that token on the server attempt. Credentials must submit the same token;
a shared cookie cannot carry another tab through the check. Refresh requires a
fresh check. A mismatch clears a prior proof.

Before activation, an atomic compare-and-set consumes the proof and removes the
encrypted username from the store, retaining only a completion tombstone. A
second request cannot consume it again. The in-flight request passes the taken
username to FEAT-IDEN-002, which rechecks the identity and the live completion
record under database locks. The tombstone retains a temporary lookup digest to
bind that exact canonical username. Expiry, replacement, a different generation
or a changed username fails closed even after a lock wait.

On a refused activation, the same value may be restored only to the still-live,
same-generation tombstone, without proof and without extending its TTL. A
collision uses the existing replacement flow. Deletion or restart prevents
restoration. If a commit failure follows erasure, the student may need to start
again; recreating expired/replaced state is prohibited.

Completion purges all attempts for that initial-claim Seat or recovery User.
Restart removes the previous browser attempt. Seat/class deletion, orphan-User
deletion, unclaim and recovery reissuance erase affected owner records under their
existing lifecycle locks before destructive mutation. If erasure is unavailable,
the lifecycle mutation fails closed. A rolled-back mutation may require repeating
setup, but must not restore erased identity data.

If the verification script is unavailable, its input and submit control remain
disabled; a no-script notice explains how to resume. The standalone page uses the
same narrowly scoped paste guard.

## VI. Privacy and observability

There is no plaintext or recoverable persistent student username in a database,
file, cookie, URL, telemetry, error, history or teacher/sysadmin retrieval path.
The username is encrypted even inside volatile memory. Only lookup/verifier
hashes enter the existing User credential columns on successful activation.

Username and typed values, lookup digests, clipboard contents and names must not
enter logs, including FEAT idempotency keys. Keys use an opaque generation/request
identifier. Optional aggregate events contain only outcome, attempt count, flow
and accommodation flag. Setup responses use `Cache-Control: no-store` and
`Referrer-Policy: same-origin`: HTTPS CSRF validation retains the required
same-origin referrer, while cross-origin requests disclose none. Setup URLs
contain no username. CSRF tokens and strict HTTPS origin checks remain required.

The earlier draft's NC-IDEN-001-1 (readable username cookie) is resolved by removing
`generated_username` and cookie-held proof authority. Its regression is an ordinary
passing test, not an expected failure. Old cookie staging fields are discarded;
there is no compatibility interpretation or migration of their values.

## VII. Required verification

- `tests/dom/identity/test_username_retention_check.py`: correct/mismatched/repeated
  attempts, direct-post refusal, stable generation, collision behavior, canonical
  matching, scope/replaced-cookie failures, separate-page/tab proof, refresh,
  cookie/log/URL/database non-retention.
- `tests/test_student_setup_memory.py`: real isolated Redis; fixed TTL, encrypted
  volatile values, expiry, wrong scope, atomic concurrent consumption, guarded
  restoration, owner erasure, unavailable/unsafe store refusal.
- `tests/dom/identity/test_student_recovery.py`: User-only authorization, original
  deadline, reissuance, collisions and atomic credential replacement.
- `tests/test_username_retention_check_browser.py`: copying, hiding/re-showing,
  empty reopening, mismatch announcement/focus, paste boundary/accommodation,
  normal-login paste/password-manager semantics and rendered mobile/desktop axe.
- `tests/test_accessibility.py` and `tests/test_axe_compliance.py`: required gates;
  the latter audits the public site, not the new setup interaction.

Test results must name their exact scope. Repository tests and a supplied service
configuration do not establish that production has been provisioned or deployed.

## VIII. Amendments

Increment the version and effective date; preserve the governing invariants and
update FEAT, runtime, tests, lifecycle and operational evidence together.
