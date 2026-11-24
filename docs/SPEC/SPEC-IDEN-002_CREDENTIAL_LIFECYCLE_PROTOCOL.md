# SPEC-IDEN-002: Credential Lifecycle Protocol

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| SPEC-IDEN-002 | 1.0 | 2026-11-23 | N/A (new) | Technical Specification |

## I. Purpose

Specify the owner-approved credential lifecycle protocol, minimal operation state,
provider failure handling and acceptance evidence without conflating local atomicity
with external-provider consistency.

## II. Scope

Principal-scoped maintenance, shared teacher/sysadmin assertion validation, signup
authorization, SATAR supersession, account destruction and both reconciliation modes.
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
the principal generation; later optional passkey activation invalidates the signup session.
No provider inventory entry may be imported as an activated binding.

### Workflow stages

Each operation has an immutable purpose and target plus a constrained stage:

| Stage | Permitted action |
|---|---|
| Authorized | Perform the specifically authorized interactive preparation within session/deadline/generation bounds. |
| Registration pending | Obtain and verify the single new registration; protect ambiguous unknown-ID provider records; no authentication authority. |
| Candidate verified | Stage exact verified credential/seed and revalidate before activation or retirement intent. |
| Retirement committed | Complete only the exact recorded remote retirement and subsequent local completion, including after session expiry. |
| Provider result uncertain | Re-read inventory/retry the same target; no new discretionary target or presumed success. |
| Completed | Return the bounded receipt only; no repeat generation/session effect. |
| Cancelled/expired/superseded | No activation; only authorized erasure and remote retirement of abandoned material. |

Stage names are logical states, not a requirement for a particular ORM representation.
Do not accept browser-supplied stage, principal, generation or pending secret as authority.
Interactive lifetime is fixed: ten minutes maximum, or five for signup, capped by session
validity. Every request and completion rechecks it. New provider tokens must not outlive
the applicable registration deadline. Retries never renew the operation.

Only one discretionary credential operation is current per principal. A new operation
cannot adopt a credential reserved for another operation's retirement. SATAR and destruction
may supersede routine work; no stale continuation can activate into the new generation.
Use uniqueness plus locked transitions, not read-then-act or durable audit history, for
idempotency. Keep a completed operation's minimal receipt only until its original
interactive deadline; erase secret/provider-target material as soon as no work needs it.
An expired receipt cannot authorize re-execution; a replay then fails closed.

### Transactions and provider I/O

Use short local transactions to authorize/reserve exact work and record intent. Close
all database transactions and release database row locks before provider calls and retry
delays. Revalidate current principal existence, generation, session when applicable,
stage and supersession in a new local transaction before recording/activating results.
No local rollback promise extends to provider effects.

Serialization must coordinate registration, replacement, removal, recovery, destruction
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
| Capability/challenge verifier | Purpose-bound, single-use proof; sensitive verifier | Purpose-separated nonreversible verifier | Erase when consumed, expired or superseded; never retain raw token |
| Authorization deadline | Fixed interactive lifetime; nonsecret metadata | Canonical UTC timestamp | Operation lifetime; never extend |
| Pending TOTP seed | Validate candidate authenticator; authentication secret | Approved encryption only | Erase upon activation, cancellation, expiry or supersession; no old-secret copy |
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
mode runs at initial/additional enrollment, selected replacement, removal, SATAR and
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
- Live unknown-ID registrations are protected, and concurrent enrollment/replacement
  cannot cause a lawful credential to be deleted.
- Failed/truncated inventory, pagination gaps, permission failures and local database
  unavailability produce no destructive false positives or false readiness claim.
- Unexpected remote absence does not silently mutate the local registry.
- Interrupted execution and lost responses are idempotent. Exact remote-before-local
  retirement remains enforced for ordinary replacement/removal.

### Lifecycle and authority

- Both replacement types, enrollment and removal invalidate sessions/challenges once;
  retries/reconciliation do not invalidate subsequently established sessions.
- SATAR initiation does not revoke authority; aggregate success supersedes routine work
  before and after remote-retirement intent. Stale work cannot activate after recovery.
- Fixed reconciliation continues after session expiry without renewing/creating a session.
- Maintenance succeeds without active class selection but grants no classroom authority.
- Signup authorization requires explicit prior election and cannot be replayed, duplicated,
  renewed, regenerated from login or repurposed; skip preserves the signup session.
- Principal destruction during provider work cannot restore local authority. Outage,
  transient/permanent failure and the 15-second/three-attempt cap preserve lawful local
  destruction, while local auth/database/audit failures prevent false completion.
- No database transaction/row lock is open during provider calls or retry delays.
- TOTP cancellation/wrong code/expiry/commit failure preserves the old secret; successful
  activation overwrites it. No fallback/backup-code path is introduced.
- Replacement B→D among A/B/C preserves A/C; remote retirement followed by local failure
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
proposals. The initial 2026-11-23 issue records owner adjudications, not deployed behavior.
