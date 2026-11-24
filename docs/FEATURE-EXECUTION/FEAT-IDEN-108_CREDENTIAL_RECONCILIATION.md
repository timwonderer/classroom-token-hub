# FEAT-IDEN-108: Credential Reconciliation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-IDEN-108 | 1.0 | 2026-11-23 | N/A (new) | Normative |

## I. Purpose

Reconcile current external credential inventory with CTH authority without deriving authentication authority from provider records.

## II. Scope

Operation-triggered principal-scoped and scheduled system-scoped reconciliation through one canonical Identity implementation. No classroom reads or mutations.

## III. Authority Level

Execution-level contract subordinate to INV-CORE-000/001, INV-ARC-001/003/006/007/019,
and DOM-IDEN-003/005. No implementation behavior overrides that authority.

## IV. Dependencies

- [DOM-IDEN-003 — Teacher Identity Architecture](../DOMAIN/DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md), §VII.A and §IX.
- [DOM-IDEN-005 — Identity Binding and Lifecycle](../DOMAIN/DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md).
- [FEAT-CORE-000](FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md), declared execution scopes and workflows.
- [SPEC-IDEN-002 — Credential Lifecycle Protocol](../SPEC/SPEC-IDEN-002_CREDENTIAL_LIFECYCLE_PROTOCOL.md), incorporated by DOM-IDEN-003.
- [SPEC-SEC-001](../SPEC/SPEC-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_CODE_CONTRACT.md).
- [DOM-OPS-002](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md), §2.5 outcome envelope.

## V. Execution authority

Declare the FEAT-CORE-000 credential-reconciliation category. An autonomous execution
uses either a fixed recorded operation or the scheduled provider-consistency policy,
not an expired teacher session, sysadmin role or classroom context. Interactive lifecycle
FEATs use the same domain commands inside their own orchestration; they never invoke
this FEAT executor. Scope and generation/stage are evaluated from current Identity state.

For existing principals, read only principal eligibility, activated credentials and
lawful pending/retirement state. For absent principals, evaluate provider inventory
against current local absence without creating a principal, tombstone or history row.
Use exact identifiers internally, never in persistent outcome evidence.

## VI. Canonical reconciliation commands

1. Obtain complete usable provider inventory for the evaluation scope. Failed, partial,
   malformed or uncertain inventory grants no deletion authority.
2. Classify exact credentials as active, pending, retiring, provider-only or unexpectedly
   absent remotely. Protect unknown-ID lawful pending registrations; do not guess their
   resulting credential from inventory. Uncertainty defers destructive classification.
3. Coordinate with the per-principal operation boundary and revalidate local eligibility
   before destructive action. Commit any required live-principal fixed intent, release
   the transaction/row locks, then perform exact remote deletion. Reserve the target
   against new local activation while deletion is in flight. At the next local transaction
   boundary recheck generation, stage and supersession before accepting the result.
4. Preserve active bindings. Unexpected remote absence is reported, never automatic local
   deletion/import. A fixed authorized continuation can complete its recorded local change;
   the generic scheduled inventory sweep cannot invent such authority.
5. Resolve lost responses idempotently through fresh inventory. Emit non-identifying
   outcome evidence for attempts, failures, retries and completion. Superseded operations
   may clean up, never activate. Never repeat a completed generation/session transition.

Principal mode is limited to its exact target and runs at enrollment, replacement,
removal, SATAR and destruction boundaries. Destruction expects an empty surviving
provider set and uses FEAT-IDEN-007's provider-failure exception, not an eternal retry hold.

Scheduled mode enumerates the configured provider tenant, then exact per-user inventory.
It discovers late registrations and orphaned credentials without retained local identity
history. Reuse the tenant-orphan tool's inventory integration through these commands;
no alternate direct-delete script is authorized. Provider-user/alias removal is allowed
only for a revalidated absent/destroying local principal, never as a shortcut to replace
one passkey on a surviving account. Interrupted orphan discovery is restarted from
current provider inventory, not a persisted list of destroyed principal IDs.

## VII. Failure, retention and enablement

No database transaction or row lock spans provider calls or retries. Failed inventory
never means empty; absent local data caused by an unavailable database never means an
orphan. System scope is restricted to Identity/provider state. No cleanup may restore
or recreate local authority. Provider-only residue remains unable to authenticate even
when this execution is down.

Retain minimal current-operation state only while lawful work remains and its principal
exists. Destroy it with the principal. Secret material is not retained for remote cleanup.
Generic scheduled sweeps retain no historical identity list, inventory archive or cursor
that reconstructs deleted ownership. Use only DOM-OPS-002 §2.5 evidence.

Before destructive scheduling is enabled, verify real integration inventory completeness,
pagination, tenant isolation/permissions and exact deletion semantics, including already
absent credentials and uncertain responses. Mock success does not establish readiness.
Cadence, scheduling and retry implementation are proposed in the review record, not
new foundational invariants. All executions remain explicit auditable FEAT commands.

## VIII. Required validation

Implement the full SPEC-IDEN-002 matrix: every lifecycle boundary, scheduled orphan and
late-registration discovery, absent-principal cleanup without tombstones, pending unknown
IDs, concurrent registration/replacement, exact scope, incomplete inventories, unavailable
local database, unexpected remote absence, uncertain delete outcomes, idempotency,
supersession, expired-session continuation, no authority reconstruction, no open database
transaction/row lock during provider I/O, and observability deletion compliance.

## IX. Amendment

Increment version and effective date, preserve the INV → DOM → FEAT hierarchy,
and update SOP-DOC-001 and dependent references. This 2026-11-23 revision records
the approved lifecycle contract; it does not claim implemented or deployed behavior.
