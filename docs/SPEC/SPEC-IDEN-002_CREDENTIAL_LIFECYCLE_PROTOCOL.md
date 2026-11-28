# SPEC-IDEN-002: Credential Lifecycle Protocol

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| SPEC-IDEN-002 | 1.4 | 2026-11-27 | 1.3 | Technical Specification |

## I. Purpose

Specify the owner-approved credential lifecycle protocol, minimal operation state,
provider failure handling and acceptance evidence without conflating local atomicity
with external-provider consistency.

## II. Scope

Principal-scoped maintenance, shared teacher/sysadmin assertion validation, SATAR supersession, account destruction and both reconciliation modes.
No classroom authority or additional recovery mechanism is created.

## III. Authority Level

Binding where incorporated by DOM-IDEN-003 §VII.A and INV-ARC-019 §VI. Subordinate to
INV-CORE, INV-ARC and DOM authority. Schema/adapter choices in the implementation proposal
are descriptive until separately implemented and verified.

## IV. Dependencies

- [INV-ARC-019](../INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md), credential ownership and activation.
- [DOM-IDEN-003](../DOMAIN/DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md), §VII.A lifecycle policy and §IX SATAR.
- [DOM-IDEN-005](../DOMAIN/DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md), lawful destruction.
- [FEAT-CORE-000](../FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md), scope and workflow execution.
- [SPEC-SEC-001](SPEC-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_CODE_CONTRACT.md), secret/verifier representation.
- [DOM-OPS-002](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md), §2.5 outcome envelope.

## V. Protocol and local authority

### Proof and activation

Every externally verified assertion requires pure evaluation of the existing principal,
exact local credential ownership, lawful committed activation, intended purpose, expiry,
replay protection and current generation. A valid provider assertion for a pending,
unknown, revoked, superseded or foreign credential fails closed. Verify role and expected
principal where the flow began from a username. Registration tokens cannot sign in;
login proof cannot silently become operation authorization. Assert expected origin/RP
and ceremony/challenge binding through the verified integration contract.

Commands consuming proof recheck current state at the mutation boundary. Pure evaluation
does not consume a challenge, change `last_used`, emit audit or establish a session.
Those are explicit post-validation commands. Successful credential activation/removal
advances generation and revokes sessions/challenges/management authorizations atomically
with its local changes and mandatory audit. A completed retry has none of those effects.

The registry contains only lawful activated bindings; pending material belongs to current
operation state and cannot be accepted by registry readers. Initial signup initializes
the principal generation; later passkey activation invalidates the signup session.
No provider inventory entry may be imported as an activated binding.

### Workflow stages

Each operation has an immutable purpose and target plus a constrained stage:

| Stage | Permitted action |
|---|---|
| Awaiting step-up | TOTP replacement only: hold the single-use step-up challenge and its window; accept only qualifying step-up evidence (below); no pending seed, no authority over any credential. |
| Authorized | Perform the specifically authorized interactive preparation within session/deadline/generation bounds. |
| Registration pending | Obtain and verify the single new registration; protect ambiguous unknown-ID provider records; no authentication authority. |
| Candidate verified | Stage exact verified credential/seed and revalidate before activation or retirement intent. |
| Retirement committed | Complete only the exact recorded remote retirement and subsequent local completion, including after session expiry. |
| Provider result uncertain | Re-read inventory/retry the same target; no new discretionary target or presumed success. |
| Completed | Return the bounded receipt only; no repeat generation/session effect. |
| Cancelled/expired/superseded | No activation; only authorized erasure and remote retirement of abandoned material. |

Stage names are logical states, not a requirement for a particular ORM representation.
Do not accept browser-supplied stage, principal, generation or pending secret as authority.
Interactive lifetime is fixed: ten minutes maximum, capped by session
validity. Every new request and every uncommitted completion rechecks it; a retirement committed
before the deadline and its local completion are exempt from the deadline and session expiry,
and still check the recorded target, generation and supersession state. New provider tokens must not outlive
the applicable registration deadline. Retries never renew the operation.

Only one discretionary credential operation is current per principal. A new operation
cannot adopt a credential reserved for another operation's retirement. SATAR and destruction
may supersede routine work; no stale continuation can activate into the new generation.
Use uniqueness plus locked transitions, not read-then-act or durable audit history, for
idempotency. Keep a completed operation's minimal receipt only until its original
interactive deadline (and, where it consumed step-up evidence, until that evidence's retention time, below);
erase secret/provider-target material as soon as no work needs it.
An expired receipt cannot authorize re-execution; a replay then fails closed.

### TOTP replacement step-up evidence

**Rule.** TOTP replacement (FEAT-IDEN-106) is authorized only by dedicated provider step-up
evidence consumed under this subsection. An ordinary sign-in token never authorizes it,
however recent. The TOTP never authorizes its own replacement.

**Four kinds of assurance, kept distinct.** (1) *Provider-authenticated evidence*: the
passwordless.dev `/signin/verify` response for the principal's credential. (2) *CTH-enforced
operation authorization*: CTH's own locked consumption of that evidence against a stored,
single-use challenge on the principal's one TOTP_REPLACE operation. (3) *Provider-dependent user
verification*: the `totp-replace` authentication configuration requires it, the authenticator
asserts it by its own policy (it may reflect an earlier unlock and is not fresh consent), and the
token does not carry it, so CTH cannot observe it. (4) *Cryptographic operation binding*: not
supported. The token names neither this operation nor this challenge; the stored challenge and its
window are CTH's own timing bound, not a signature over the operation.

Constants: **W** = 120 s (challenge window), **L** = 120 s (longest accepted token lifetime),
**S** = 10 s (clock skew, used only where stated). Every local clock reading, comparison,
duration, expiry and retention time is a canonical temporal resolver primitive (INV-ARC-015,
SPEC-TIME-001); provider timestamps are parsed once, at the boundary, to the resolver's instant type.

1. **Challenge.** Before the ceremony, CTH stores on the principal's one current TOTP_REPLACE
   operation (stage *awaiting step-up*) a single-use challenge verifier, its issue instant `t0`, and
   `c = min(t0 + W, operation deadline)`. It is bound to the existing session verifier, the authorized
   generation, the operation ID and the purpose. It is a stored challenge, not the stateless bucketed
   challenge, which remains for TOTP-authorized passkey work. A new challenge on the same operation
   replaces the verifier; the earlier one is dead.
2. **Provider configuration precondition.** A challenge is issued, and evidence consumed, only while a
   point-of-use check of the provider's authentication configurations passes: exactly one `totp-replace`
   configuration, user verification `required`, `timeToLive` at most L. Anything else, including an
   unreachable or malformed reply, a missing or a duplicated entry, fails TOTP replacement closed with a
   non-identifying diagnostic and a coarse log category. The check is made twice per replacement (before the
   challenge, and after the token is verified and before the consuming transaction), outside any database
   transaction, never cached, with no startup or periodic check. Sign-in and every other credential
   operation are unaffected; no application-wide failure results. A configuration relaxed and then restored
   between the two checks requires provider administrative access, which is already full passkey compromise;
   this is documented, not mitigated. The lifetime bound is also enforced from the evidence itself (rule 4).
3. **Parsing.** The response is parsed from the raw JSON. A missing, null, mistyped or unparseable
   `success`, `purpose`, `type`, `userId`, `credentialId`, `origin`, `rpId`, `timestamp`, `expiresAt` or
   `tokenId` fails closed. Nothing is inferred from stored metadata.
4. **Pure evaluation** (clock from the resolver; reads, writes nothing). All of: `success` is true;
   `purpose` equals `totp-replace` exactly; `type` equals `passkey_signin` exactly; `origin` and `rpId` equal
   the configured values exactly; `userId` is the principal's provider user ID; the canonical `credentialId`
   is a lawfully activated passkey of the principal; `t0 <= timestamp <= c` (no skew on the lower bound);
   `timestamp <= now + S`; `0 < expiresAt - timestamp <= L`; `now < expiresAt` and `now < c` (no skew).
5. **Consumption.** One local transaction, opened after the provider calls. It locks the principal row, then
   the operation row (the order every credential command uses). Only after both locks does it take a fresh
   clock reading; the evaluation's reading is never reused. It requires: the principal exists; the stage is
   *awaiting step-up* and a challenge verifier is present; the submitted challenge matches the stored verifier
   (constant time); `now < c` and `now < expiresAt`; `timestamp <= now + S`; the session verifier matches the
   current sign-in; the principal's generation equals the operation's authorized generation; and the passkey
   binding for the `credentialId`, re-read in this transaction, exists, is the principal's and is activated.
   It then records the token ID and the retention time, erases the challenge verifier and moves the operation
   to *Authorized*, in the same commit. The first failing check decides the refusal. A unique-index violation
   on the token ID is the final guard: the transaction rolls back and the request fails closed.
6. **Failure preserves the TOTP.** No authorization failure touches the TOTP credential, the credential
   generation or any session.
7. **Time.** All comparisons, durations, expiries and retention are resolver primitives; no parallel time logic.

**Retention.** `step_up_retain_until = expiresAt + S`, stored at consumption, so a token can qualify no later
than about S + L after consumption. The token ID is unique across every row, not only live ones. The expiry sweep
may delete a terminal operation only when its deadline has passed and its retention time is absent or has passed.
Cancellation, expiry and supersession change the stage and never delete. Principal destruction removes the rows
with the principal (ON DELETE CASCADE) and takes the principal lock before any other row, so it cannot invert the
consumption's lock order. S covers a bounded clock correction (at most 10 s, such as an NTP step), not an
arbitrary rollback of the clock.

**Provider behavior relied on** (observed on the staging tenant, 2026-11-27): an unknown purpose silently becomes
`sign-in`; provider tokens are not single use and may be verified again until they expire; the token carries no
user-verification flag; the Python SDK's verified-user object drops `purpose`, so CTH parses the raw response.

### Transactions and provider I/O

Use short local transactions to authorize/reserve exact work and record intent. Close
all database transactions and release database row locks before provider calls and retry
delays. Revalidate current principal existence, generation, session when applicable,
stage and supersession in a new local transaction before recording/activating results.
No local rollback promise extends to provider effects.

Serialization must coordinate registration, TOTP replacement, removal, recovery, destruction
and both reconciliation modes. A durable reservation prevents a target from acquiring
new local authority while its remote deletion is in flight. Recovery/destruction can
supersede the reservation but cannot revive it. Process-local locking alone is insufficient.
The concrete cross-worker coordination mechanism is an implementation decision to review;
it must satisfy these properties without a database row lock spanning network work.

For a provider principal without a local row, recheck absence from an available authoritative
database before deletion; never create a principal/tombstone to coordinate cleanup.
No provider callback or reconciliation command can reconstruct a deleted principal.

## VI. Persistent operation-state inventory

Identity is the authoritative owner of every field below. `credential_operations.user_id`
is the only new principal reference allowlisted for this protocol. It is removed with
the principal and never copied into operational history. Fields may be nullable when
irrelevant to an operation. No generic JSON provider-response archive is authorized.

| Logical field | Functional necessity / classification | Permitted storage | Retention / destruction |
|---|---|---|---|
| Principal credential generation | Reject stale challenges and mutations; nonsecret security state | Monotonic integer on principal | Principal lifetime only; never reset/reuse after destruction |
| Operation ID | Fixed operation and idempotency; nonsecret operational state | Independently random UUID, not authority alone | Active work or bounded completion receipt; delete with principal |
| Principal owner | Current ownership; internal identity association | Exact UUID FK, never log/export | Delete with principal; no historical copy |
| Purpose and stage | Limit transitions; nonsecret operational state | Closed enums | Until work ends / bounded receipt expires |
| Authorized generation | Prevent stale activation; nonsecret security state | Integer snapshot | Until operation/receipt erased |
| Session binding verifier | Bind interactive authorization; sensitive verifier | Purpose-separated nonreversible verifier | Erase on interactive expiry, consumption into retirement intent or supersession |
| Challenge verifier | Purpose-bound, single-use proof; sensitive verifier | Purpose-separated nonreversible verifier | Erase when consumed, expired or superseded; never retain raw token |
| Step-up challenge issue time and window end | Bound the evidence that qualifies (`t0`, `c`); nonsecret metadata | Canonical UTC timestamps | Operation lifetime; never extend past the deadline |
| Consumed step-up token ID | Replay prevention; nonsecret operational state | Provider token UUID, unique across all operation rows | Until the evidence retention time has passed and the operation is deleted; delete with principal |
| Step-up evidence retention time | Keeps a spent token ID refusing replay for as long as it could qualify; nonsecret metadata | Canonical UTC timestamp (`expiresAt + S`) | Until the sweep deletes the row; delete with principal |
| Authorization deadline | Fixed interactive lifetime; nonsecret metadata | Canonical UTC timestamp | Operation lifetime; never extend |
| Pending TOTP seed (generated per SPEC-SEC-001 §V seed-length requirement) | Validate candidate authenticator; authentication secret | Approved encryption only | Erase upon activation, cancellation, expiry or supersession; no old-secret copy |
| Old/new credential IDs | Exact provider work; credential metadata | Exact identifiers inside Identity only | While fixed retirement/activation work needs them; delete with principal |
| Provider issuance deadline/status | Protect unknown-ID pending registration; operational metadata | Fixed UTC deadline and bounded state | Until issuance ambiguity ends or principal is destroyed |
| Retirement intent/result | Retry exact work; nonsecret operational state with target binding above | Fixed purpose/targets, timestamp, bounded outcome | Until verified completion/supersession cleanup or principal destruction |
| Retry scheduling | Resume incomplete work; nonsecret metadata | Next-attempt time, counter, coarse error category | Erase at terminal cleanup; no raw exception/response archive |

No class/Seat, PII, username, device fingerprint, public-key archive, credential label or
contact information is added to operation state. Credential display labels remain only
in their governed credential record and are never authority or audit fields.

Secrets/verifiers immediately lose operational authority at expiry/consumption/supersession.
Physical erasure occurs at the earliest lawful cleanup execution. One minute is an
operational target, with failures visible and retryable, not an unconditional guarantee
under infrastructure unavailability. No pending secret may survive solely because
nonsecret provider reconciliation remains outstanding. Principal destruction erases all
associated state, regardless of provider cleanup status.

Audit/correlation identifiers cannot independently reconstruct ownership. Any live
association in operation state is deleted with that state; secondary storage must not
preserve the association. Secret and identity-derived digests are not audit substitutes.

## VII. Reconciliation and provider boundaries

Both modes use the same pure classification and explicit retirement commands. Principal
mode runs at initial/additional enrollment, removal, SATAR and
destruction boundaries. Scheduled mode reads the configured provider tenant inventory
and compares each exact provider principal/credential against current local authority.
It grants no access to classroom data. Provider-only records never become local authority.

Protect activated bindings and live pending work. While a bounded registration is lawful
but its credential ID unknown, defer deletion of ambiguous provider-only entries for that
principal. Once resolved/expired/superseded, classify anew. Never guess ownership from
labels, timestamps or returned cryptographic keys. Revalidate before destructive action.
Unexpected remote absence does not remove a lawful local binding; report the discrepancy.

Inventory errors, truncation, incomplete pagination, malformed replies, unavailable local
state and uncertain tenant scope fail safe. They never mean an empty set. Lost deletion
responses require fresh inventory or safe exact retry. Verify provider-specific absent-ID
responses before treating them as idempotent success. Destructive scheduled reconciliation
requires real integration proof of completeness, pagination, tenant permissions/isolation
and exact credential deletion behavior. Mock tests are not that proof.

The provider inventory supplies the orphan-discovery set; no historical principal registry,
post-deletion cursor/target list or local ownership archive may replace it. Interrupted
scheduled discovery restarts from current inventory. Late credentials after local
principal destruction remain unable to authenticate and are retired on a later successful
sweep. Point-in-time reconciliation does not prove no future provider registration.

## VIII. Account-destruction provider budget and reporting

The total provider-work budget is **at most 15 seconds**, including all provider calls,
timeouts and retry delays, with **at most three attempts for transient failures** within
that total. Fifteen seconds is a maximum, not a mandatory wait. Permanent rejection is
not blindly retried. Do not reset the budget for each credential, call or helper. A
large/unavailable cleanup can exhaust the budget; it is not permission to retain data.
These are operational limits of this specification, not foundational invariants.

Revoke authentication/supersede operations at destruction start, attempt known remote
retirement/provider-user deletion and empty-set principal reconciliation, then revalidate
local destruction authority and execute the existing atomic lifecycle command. No database
transaction or row lock spans the external work. Bounded provider failure permits local
destruction with external cleanup unverified. Local authorization, database or mandatory
audit failure does not qualify for that exception. Ordinary credential replacement,
removal and SATAR completion retain remote-first retirement without this exception.

| Local outcome | Provider outcome | Required presentation |
|---|---|---|
| Destroyed | Cleanup verified at execution | Account deleted |
| Destroyed | Cleanup unverified | Account deleted; external passkey cleanup could not be verified |
| Not destroyed | Any | Account deletion did not complete |

Do not retain a principal, secret or target reference to later update that message.
Scheduled provider-wide reconciliation independently discovers residue. Failed local
completion must not be reported as successful just because external retirement succeeded.

## IX. Required targeted validation

### Authentication authority

- Valid provider assertions for unknown IDs, foreign ownership, missing principals,
  pending, deleted or superseded credentials are denied on teacher/sysadmin sign-in,
  step-up and TOTP-replacement surfaces.
- Wrong type, purpose, origin/RP, challenge, expiry, replay and stale generation fail
  closed. Consuming commands reject responses arriving after a generation change.
- Pure validation performs no credential, usage, session, challenge or audit mutation.
  Reconciliation unavailability cannot weaken local denial.

### Reconciliation

- Every declared lifecycle boundary invokes principal reconciliation; scope never
  reaches another principal or classroom.
- Scheduled reconciliation removes provider-only residue, including late registrations
  after destruction without surviving principal records, ownership history or tombstones.
- Live unknown-ID registrations are protected, and concurrent enrollment/removal
  cannot cause a lawful credential to be deleted.
- Failed/truncated inventory, pagination gaps, permission failures and local database
  unavailability produce no destructive false positives or false readiness claim.
- Unexpected remote absence does not silently mutate the local registry.
- Interrupted execution and lost responses are idempotent. Exact remote-before-local
  retirement remains enforced for ordinary removal.

### TOTP replacement step-up evidence

- A valid `totp-replace` step-up token authorizes the operation; the TOTP, generation and sessions are unchanged until activation.
- Refused with the TOTP, generation and sessions unchanged: a fresh ordinary sign-in token, the generic step-up preset, a missing, empty or unknown purpose; each required field missing, null, mistyped or unparseable; a different principal, provider user or credential owner; an inactive or pending credential; a wrong origin or RP ID; a different session; a submitted challenge other than the stored one. Timestamp one millisecond before `t0` is refused and exactly `t0` and exactly `c` are accepted, one millisecond after `c` refused; `now + S` accepted, one millisecond more refused; a lifetime of exactly L accepted, one millisecond more, zero or negative refused; `now` equal to `expiresAt` or to `c` refused.
- Expiry between evaluation and consumption is refused (pinned clock), and a consumption that waited for a held principal lock reads the clock after the wait.
- Replay is refused on the first failing check: the same token on the same operation after authorization (stage); a replaced or consumed challenge with a new token (challenge); the same token on a new operation after completion, cancellation or expiry (timestamp precedes the new `t0`), including after a sweep before the retention time (row still present) and after `expiresAt` (expired).
- The unique token ID index alone refuses otherwise qualifying evidence carrying a consumed ID, shown by mutation (SOP-TEST-003 §IX.A).
- The sweep deletes a spent row after its retention time and keeps it before.
- Two connections: the same token twice, and one challenge with two tokens, commit once; consumption racing passkey retirement, recovery and account destruction (both entry paths) authorizes nothing against a destroyed principal, retired credential or advanced generation, each shown failing with its lock or recheck removed.
- A missing, duplicated, user-verification-preferred, over-lifetime or unreachable `totp-replace` configuration refuses replacement while sign-in works.
- Every deletion of `credential_operations` rows is the sweep or principal destruction, with mutation proof.
- The SPEC-TIME-001 guard passes.
- These are test requirements. They are not evidence of a live-provider ceremony; that requires its own staging run.

### Lifecycle and authority

- TOTP replacement, passkey enrollment and passkey removal invalidate sessions/challenges once;
  retries/reconciliation do not invalidate subsequently established sessions.
- SATAR initiation does not revoke authority; aggregate success supersedes routine work
  before and after remote-retirement intent. Stale work cannot activate after recovery.
- Fixed reconciliation continues after session expiry without renewing/creating a session.
- Maintenance succeeds without active class selection but grants no classroom authority.
- Signup issues no enrollment authorization; deferring enrollment preserves the signup session and leaves the principal noncompliant.
- Principal destruction during provider work cannot restore local authority. Outage,
  transient/permanent failure and the 15-second/three-attempt cap preserve lawful local
  destruction, while local auth/database/audit failures prevent false completion.
- No database transaction/row lock is open during provider calls or retry delays.
- TOTP cancellation/wrong code/expiry/commit failure preserves the old secret; successful
  activation overwrites it. No fallback/backup-code path is introduced.
- Revoking B among A/B/C preserves A/C; remote retirement followed by local failure
  is accurately pending, not falsely rolled back.
- Secrets lose authority immediately; erasure failures are observable and retried. Terminal
  operation/identity deletion removes recoverable associations from logs, correlation packs,
  exports and indexes. Immutable non-identifying outcome evidence retains no ownership map.
- Preserve GHSA tests, CSRF, rate limits, generic failure responses, canonical fixtures,
  migration idempotency and accessible QR/manual-entry/pending/error/success flows.

Inspect prior pytest_result evidence first; run focused tests, not the full suite. Separate
source/SDK evidence, fake-provider fault tests, isolated provider experiments, and verified
production readiness. No destructive production experiment is implied by this contract.

## X. Amendment

Increment version/date, reconcile the owning INV/DOM and affected FEAT contracts, update
SOP-DOC-001, and preserve the distinction between approved requirements and implementation
proposals. The 2026-11-27 revision (v1.4) adds the TOTP replacement step-up evidence subsection (§V), the *awaiting step-up* stage, the step-up challenge, consumed-token and retention rows (§VI) and their validation list (§IX): TOTP replacement is authorized by provider step-up evidence consumed against a stored single-use challenge, not by the stateless challenge and a sign-in token. The earlier 2026-11-27 revision (v1.3; Owner ruling 2026-11-27: passkey replacement removed; replacement is enrollment followed by revocation) removes the passkey replacement purpose and its stages; the `passkey_replace` purpose value is retired. An earlier 2026-11-27 revision (owner authorization 2026-11-27) removes the signup-derived enrollment authorization and its five-minute lifetime; reservation, cancellation, expiry and stale-operation rules are unchanged. The 2026-11-26 revision applies the owner rulings on mandatory dual enrollment and the seed-length floor. The initial 2026-11-23 issue records owner adjudications, not deployed behavior.
