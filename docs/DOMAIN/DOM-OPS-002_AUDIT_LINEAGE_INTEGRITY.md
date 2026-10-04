# DOM-OPS-002: Audit Lineage Integrity

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|:---|:---|:---|:---|:---|
| DOM-OPS-002 | 1.10 | 2026-10-04 | 1.9 | Constitutional |

---

## I. Purpose

Define the Operations domain's authority over the tamper-evident audit lineage system: the schema, emission protocol, chain verification logic, integrity status reporting, and execution evidence model that operationalize `INV-ARC-016`.

---

## II. Scope

Governs the `audit_events`, `chain_heads`, and `integrity_status` tables and all code paths that read from or write to them.

Applies to every protected table whose mutations must produce an `AuditEvent` chain entry, including constitutional economic policy lineage objects.

---

## III. Authority Level

Constitutional. Subordinate to `INV-ARC-016` and `DOM-OPS-001`. Supersedes any prior informal convention regarding audit logging for protected tables.

---

## IV. Dependencies

- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `DOM-OPS-001_OPERATIONS_DOMAIN.md`
- `INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`
- `FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`

---

## 1. Domain Authority Declaration

### DOM-OPS-002 OWNS Authority Over

- **AuditEvent chain schema** — the structure of `audit_events` and `chain_heads`
- **Emission protocol** — the rules governing when and how `emit_audit_event()` is called
- **Chain verification logic** — the algorithm for walking a chain scope and detecting tampering
- **IntegrityStatus** — the singleton operational status record consumed by the Operations status-signal pipeline
- **Protected fields registry** — the declaration of which fields per table are included in `payload_digest`
- **Lawful write path enumeration** — what constitutes a valid execution context for chain emission

### DOM-OPS-002 Explicitly DOES NOT Own

- Business domain truth (balances, attendance, purchases)
- Constitutional economic policy truth (owned by DOM-CLASS / DOM-ECON governance)
- Feature enablement policy
- General operational telemetry and structured logs (owned by `DOM-OPS-001`)
- Incident lifecycle management (owned by `DOM-OPS-001`)

---

## 2. Schema Authority

### 2.1 `audit_events` (Append-Only)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | Integer | No | Primary key |
| `chain_scope` | String(64) | No | `"class:{uuid}"` or `"system"` |
| `sequence_number` | Integer | No | Monotonically increasing per scope |
| `previous_hash` | String(64) | No | `"genesis"` for first entry |
| `event_hash` | String(64) | No | HMAC-SHA256; unique across all events |
| `table_name` | String(64) | No | Protected table name |
| `row_pk` | String(64) | No | String-cast primary key of the protected row |
| `operation` | String(16) | No | `INSERT` / `UPDATE` / `DELETE` / `TRANSITION` |
| `actor_type` | String(32) | Yes | `"teacher"` / `"student"` / `"system"` |
| `actor_id_hash` | String(64) | Yes | Hashed seat actor identifier; never a User identifier |
| `class_id` | String(36) | Yes | UUID of the owning class |
| `seat_id` | Integer | Yes | Seat anchor if applicable |
| `feat_id` | String(32) | Yes | Active FEAT name at emit time |
| `idempotency_key` | String(128) | Yes | Caller-provided idempotency key |
| `correlation_id` | String(64) | Yes | Propagated from the active FEAT context |
| `request_id` | String(64) | Yes | HTTP request identifier |
| `payload_digest` | String(64) | No | SHA-256 of canonical protected field values |
| `context_digest` | String(64) | No | SHA-256 of actor context fields |
| `created_at_utc` | DateTime(tz) | No | UTC timestamp of emission |
| `signer_key_id` | String(16) | No | Key rotation label (e.g., `"v1"`) |
| `signature_version` | Integer | No | HMAC schema version |
| `hmac_signature` | String(64) | No | Copy of `event_hash` for fast provenance checks |

Unique constraints: `event_hash`; `(chain_scope, sequence_number)`.

### 2.2 `chain_heads`

One row per chain scope. Locked with `SELECT FOR UPDATE` on every emit to provide atomic sequence management.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `chain_scope` | String(64) | No | Primary key |
| `latest_hash` | String(64) | No | `event_hash` of the most recent event |
| `latest_sequence` | Integer | No | Most recent sequence number |
| `event_count` | Integer | No | Total events in this scope |
| `last_updated_utc` | DateTime(tz) | No | UTC timestamp of last update |

### 2.3 `integrity_status` (Single-Row Singleton)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | Integer | No | Primary key (always 1) |
| `passing` | Boolean | No | `True` only when all chains are `VERIFIED` |
| `last_checked_utc` | DateTime(tz) | Yes | UTC timestamp of last invariant check |
| `failure_detail` | Text | Yes | JSON array of failing scopes; operator-only |
| `degraded_since` | DateTime(tz) | Yes | When chain first entered failing state |

### 2.4 Allowlisted Write Paths

Only the following code paths may write to tables owned by this domain:

| Table | Allowlisted Path |
|---|---|
| `audit_events` | `app/services/audit_service.py` → `emit_audit_event()` |
| `chain_heads` | `app/services/audit_service.py` → `emit_audit_event()` |
| `integrity_status` | `app/utils/audit_verifier.py` → `update_integrity_status()` under `SystemAuditAuthority` |

Economic policy is recorded in each owning domain's own append-only table (`DOM-CLASS-003` §V); where §5.4 registers such a table as protected, its rows SHALL emit lineage exclusively through lawful FEAT-orchestrated execution paths. *(1.2: the class-wide `policy_versions` / `policy_transitions` tables formerly named here were retired by operator ruling 2026-09-30 and dropped; no audit event was ever emitted for them.)*

---

## 3. State Classification

### `audit_events`

| Field | Classification |
|---|---|
| `event_hash` | Authoritative immutable identifier |
| `payload_digest` | Authoritative integrity witness |
| `sequence_number` | Authoritative chain position |
| `previous_hash` | Authoritative chain link |
| All actor / context fields | Authoritative provenance record |

### `chain_heads`

| Field | Classification |
|---|---|
| `latest_hash` | Authoritative current chain tip |
| `latest_sequence` | Authoritative current position |
| `event_count` | Derived count |

### `integrity_status`

| Field | Classification |
|---|---|
| `passing` | Derived aggregate from nightly chain walk |
| `degraded_since` | Authoritative incident onset timestamp |
| `failure_detail` | Derived diagnostic snapshot |

---

## 4. Invariants

### INV-OPS-013: Append-Only Audit Chain

`AuditEvent` rows shall never be updated or deleted. Any `UPDATE` or `DELETE` on `audit_events` is prohibited in all environments. Detection of such a modification is an incident.

### INV-OPS-014: Single Legal Emit Path

`emit_audit_event()` in `app/services/audit_service.py` is the only legal write path for `audit_events`. No other code may produce `AuditEvent` rows directly.

### INV-OPS-015: FEAT Context Requirement

`emit_audit_event()` shall raise `AuditContextError` if called outside an active FEAT context or `SystemAuditAuthority`. Direct calls without a context are prohibited.

### INV-OPS-016: HMAC Key Availability

The `AUDIT_HMAC_KEY` environment variable shall be present at application startup. The application shall refuse to start if absent. The key shall be separate from `PEPPER_KEY` and shall never be shared between environments.

### INV-OPS-017: Chain Scope Isolation

Events for class-scoped protected tables shall use chain scope `"class:{class_id}"`. System-level events shall use chain scope `"system"`. Cross-scope chain references are prohibited.

Class-scoped protected tables include, and are not limited to:
- `transactions` — scoped by `class_id`

Any audit event for a class-scoped protected table that does not carry a valid `class_id` is a chain integrity violation.

### INV-OPS-018: UTC Normalization Requirement

All datetime values used in HMAC computation shall be normalized to UTC (`+00:00`) before `isoformat()` is called. The verifier shall apply the same normalization when recomputing event hashes. Mismatched timezone representations are an `INVALID` chain condition.

### INV-OPS-019: Payload Digest Field Parity

The `PROTECTED_FIELDS_BY_TABLE` registry in `app/utils/audit_verifier.py` shall exactly match the fields passed to `audit_protected()` at write time. Missing a field produces a false `INVALID`; an extra field produces a false `INVALID`. Both are prohibited.

### INV-OPS-020: UNVERIFIED Is Not INVALID

A row with `lineage_event_id IS NULL` shall return state `UNVERIFIED`, not `INVALID`. `UNVERIFIED` rows shall not cause `IntegrityStatus.passing` to be set to `False`. Code, logs, and operator-facing output shall never conflate these two states.

---

## 5. Schema Contract

### 5.1 Canonical Payload

The payload digest is computed over a deterministic JSON string with the following structure:

```
{
  "__table__": <table_name>,
  "__pk__": <str(row_pk)>,
  "__op__": <operation>,
  "__class_id__": <class_id or null>,
  <field_1>: <normalized_value>,
  <field_2>: <normalized_value>,
  ...
}
```

Rules:
- Business fields sorted by key.
- `datetime` values converted to UTC ISO-8601 before serialization.
- `Decimal` values converted to `str`.
- `None` values serialized as JSON `null`.
- JSON produced with `sort_keys=True`, no whitespace (`separators=(",", ":")`).

The digest is `SHA-256(canonical_json_utf8)` expressed as a 64-character hex string.

### 5.2 Context Digest

The context digest is `SHA-256` of the sorted JSON of:
`{feat_id, class_id, actor_type, actor_id_hash, correlation_id, idempotency_key}`

### 5.3 Event Hash (HMAC)

The event hash is `HMAC-SHA256(AUDIT_HMAC_KEY, message)` where `message` is pipe-delimited:

```
{previous_hash}|{chain_scope}|{sequence_number}|{table_name}|{row_pk}|{operation}|{actor_context_json}|{payload_digest}|{created_at_utc_isoformat}
```

`actor_context_json` is the sorted JSON of `{actor_type, actor_id_hash, feat_id, correlation_id}`.

### 5.4 Protected Fields Registry

| Table | Protected Fields |
|---|---|
| `transactions` | `amount`, `account_type`, `type`, `status`, `class_id`, `seat_id`, `description`, `correlation_id` |

The `transactions` row above describes the historical surface; it does not substitute for the canonical V2 `ledger_transaction` registration below.

| Canonical Table | Protected Fields |
|---|---|
| `attendance_interval_invalidation` | `id`, `class_id`, `actor_seat_id`, `target_seat_id`, `opening_event_id`, `closing_event_id`, `recorded_at`, `reason_code`, `idempotency_key`, `correlation_id`, `receipt_json` |
| `payroll_event` | `id`, `class_id`, `payroll_cycle_id`, `actor_seat_id`, `target_seat_id`, `correlation_id`, `idempotency_key`, `policy_uuid`, `mechanism`, `payroll_event_type`, `recorded_at`, `summary_json` |
| `ledger_transaction` (version 2) | `id`, `class_id`, `actor_seat_id`, `target_seat_id`, `mechanism`, `amount_cents`, `timestamp`, `account_type`, `description`, `correlation_id`, `feat_code`, `idempotency_key`, `policy_id`, `type`, `posting_sequence`, `command_reservation_id` |
| `ledger_transaction` (version 3) | `id`, `class_id`, `actor_seat_id`, `target_seat_id`, `mechanism`, `amount_cents`, `timestamp`, `account_type`, `description`, `correlation_id`, `feat_code`, `idempotency_key`, `policy_id`, `type`, `posting_sequence`, `command_reservation_id`, `compensation_origin_locator`, `compensation_amount_cents`, `correction_intent_locator` |

The row marked `ledger_transaction` (version 2) is the retained **signature version 2** registry. Every listed attribute must exist in the model/schema and emitter; signing an absent attribute as `None` is prohibited. Creation freezes all sixteen fields before INSERT, including command reservation, initiating FEAT, command key, and immutable class posting sequence. The FEAT emits that final creation payload once; cursor reconciliation and informational `posted_at` initialization do not alter it. Version 2 changes the protected payload schema, not the HMAC algorithm or key, and does not require re-signing any accepted event.

New Ledger effects use signature version 3 with exactly nineteen model/schema fields: the unchanged sixteen version-2 fields plus immutable `compensation_origin_locator`, nonnegative integer `compensation_amount_cents`, and `correction_intent_locator`. Locator columns are nullable String(128); the cent column permits NULL only on historical rows. New effects explicitly set cents (zero for non-recovery), without a default or historical backfill. These are fixed before INSERT and audit emission. Non-compensation and protection-transfer legs record zero attributable recovery and no compensation intent; a recovery leg names its opaque original credit and correction intent. The emitter and verifier select the exact registry by event signature version. Accepted version-2 rows remain verifiable against their original sixteen fields; newly present compensation fields are not retroactively added to those signatures and cannot establish historical compensation authority. Required-field coverage is evaluated against the registry of the linked event's signature version, never against the newest global registry. A version-2 signature cannot prove any of the three version-3 compensation fields merely because the model now contains them. A missing registered attribute or unsupported signature version is unavailable coverage, never a fabricated null. The HMAC algorithm and signer key are unchanged. No historical audit pointer, token, version or payload is replaced.

Historical Ledger signature version 1 retains its original field definition and hash-chain inputs. Where the retired persisted `status` input prevents faithful row-payload reconstruction, return DEGRADED with bounded `VERIFIER_COVERAGE_UNAVAILABLE` evidence; canonical creation-proof consumers return UNAVAILABLE; the distinct Ledger-owned reconstruction contract may consume authenticated original envelope/chain observations without treating them as creation proof. A non-NULL historical pointer is not relabeled UNVERIFIED (INV-ARC-016 §VI). Do not fabricate an original status, reinterpret the signature as version 2, rewrite the row, or issue a replacement signature. Historical chain verification remains unchanged; only NULL linkage denotes UNVERIFIED.

The entire `summary_json` is protected, including original interval source IDs, credited seconds, policy locators/rates, allocation version, scheduled-occurrence provenance, original payroll event, correction intent, invalidation ID, and opaque correction/monetary outcome locators. It stores no monetary amounts. The entire nonmonetary `receipt_json` is protected, including accepted preview identity, fingerprint version, intent digest, settlement disposition, and opaque original-outcome locators. Transient audit payload digests do not substitute for a durable command receipt.

These canonical registrations declare authority; they do not attest deployed verifier coverage. Each implemented protected table must register these exact fields in its emitter and verifier. Field parity under INV-OPS-019 is mandatory when implemented. Protected field changes use the lineage-version mechanism (§8.12) and must not retroactively reinterpret old signatures.

Every new invalidation, correction payroll row, and compensation effect emits once after flush and before the single FEAT commit through the existing Operations command path (§6.1); emission failure rolls back the whole business action. `lineage_event_id` is assigned by that protocol rather than hashed circularly as its own payload. The mandatory audit pointer under `INV-ARC-016` §V is narrowly scoped and grants no general exception for other-domain internal FKs. Additional tables shall be registered before implementation, in coordination with owning domain authority and lawful FEAT execution.

### 5.5 Chain Scope Resolution

```
class_id present  →  "class:{class_id}"
class_id absent   →  "system"
```

Per-class `ChainHead` rows are bootstrapped lazily on first emit for that class.

**Economic policy tables** are class-scoped. When one is registered in §5.4, its audit chain scope is always `"class:{class_id}"`; there is no system-scoped chain for economic policy. A row of one emitted without a `class_id` is an `INVALID` chain condition and MUST be surfaced in `IntegrityStatus`.

---

## 6. State Transitions

### 6.1 Chain Emit Flow

```
caller enters FEAT context
  → domain mutation executes
  → db.session.flush() (row.id assigned)
  → audit_protected() called
      → emit_audit_event() called
          → ChainHead acquired with SELECT FOR UPDATE
          → AuditEvent constructed (sequence, hashes computed)
          → AuditEvent flushed
          → ChainHead updated atomically
          → row.lineage_event_id, lineage_token, lineage_version set
          → policy transition lineage activation recorded if applicable
  → FEAT transaction commits
```

For `payroll_event` and `attendance_interval_invalidation`, the creation protocol is `INSERT → initialize complete linkage once → commit`. The owning PROD FEAT freezes every business field, including all of `summary_json` or the complete nonmonetary `receipt_json`, before INSERT. Operations emits the §5.4 payload through `audit_protected()` after flush and attaches `lineage_event_id`, `lineage_token`, and `lineage_version` together exactly once in that same creating transaction. This initialization is the sole exception to an UPDATE prohibition: business fields cannot change even before commit, and no field, including linkage, can change after commit. Only FEAT-PROD-005 may originate invalidation creation evidence. FEAT-PROD-003/004/005 may originate payroll creation evidence; FEAT-STOR-003 may do so only for its incorporated productivity-insurance `manual_credit` command (FEAT-STOR-003 §VIII, DOM-PROD-001 §VIII).

Both application and database guards SHALL reject late attachment, replacement, partial linkage, and creation without required lineage. The database defers the creation check until transaction completion and checks the final persisted row and matching creation event; Operations' application guard additionally checks the canonical protected payload digest. Privileged SQL does not become a lawful write path through satisfying structural linkage constraints; the strict verifier remains responsible for cryptographic chain and payload proof (`INV-ARC-016` §V/IX). Emission, initialization, or commit validation failure rolls back business rows, Ledger effects, and audit chain changes together. Existing lifecycle guards govern seat/class destruction. Historical NULL linkage remains UNVERIFIED and SHALL NOT be backfilled or signed by this rollout.

### 6.2 Pure Creation-Evidence Query

`verified_creation_evidence(table, row, class_id, required_fields?)` is an Operations-owned public pure query. It returns unavailable (`None`) unless strict scoped pointer/token/version, exact linked-version field coverage, current protected payload and complete class-chain/head verification all succeed. Its immutable `VerifiedCreationEvidence` contains `table_name`, `row_pk`, `class_id`, `lineage_event_id`, `lineage_token`, `signature_version`, exact `protected_fields`, and immutable `protected_values`. It contains no client-supplied verification boolean; unavailable evidence grants no authority. Missing model attributes are not synthesized as null.

For correction execution, the originating FEAT obtains the complete source/candidate requirements from Ledger, invokes this Operations query for every required record, and supplies the resulting typed scoped evidence to Ledger. Ledger matches all identities, linked versions, required coverage and protected monetary facts to its own current locked records before deriving a recovery cap or posting. Ledger does not call Operations or import its internal class/registry; this cross-domain composition belongs only to the FEAT under INV-ARC-021 §V.1/VII. The display-only exception does not authorize runtime compensation decisions.

### 6.2A Pure historical audit coverage diagnostics

The historical reconstruction FEATs also compose the unchanged canonical §6.2 query for modern sources and §6.2A observations for old sources. These observations can be accepted as coverage metadata by Ledger's separate reconstruction evidence; they do not expand original signed fields or relabel original lawfulness. Legacy NULL linkage remains UNVERIFIED. Retired v1 status that cannot be faithfully reproduced remains DEGRADED with VERIFIER_COVERAGE_UNAVAILABLE; its complete linked envelope/chain is still checked. Missing coverage differs from authenticated payload/HMAC/chain/scope contradiction, which remains INVALID and denies recovery. Coverage-only inability is not diagnosed as actual tampering; known contradictions cannot be suppressed as a coverage gap. New business and monetary writes still require complete current lawful lineage.


Operations owns `diagnose_historical_audit_coverage(table, row, class_id, *, source_descriptor=None, emitter_provenance=None, max_chain_events=1000)`, composed through FEAT-PROD-006 and directly through FEAT-PROD-005/003 reconstruction coordination. Incorporates [SPEC-PROD-002](../SPEC/SPEC-PROD-002_HISTORICAL_ATTENDANCE_PROOF_ASSESSMENT.md) §V, VII–VIII for exact original envelope/field coverage and bounded pure diagnostics. The batch query `diagnose_historical_audit_coverages(table, rows, class_id, *, max_chain_events=1000, max_rows=1000)` returns one immutable observation per scoped row and walks the complete class chain once per invocation. Both budgets are positive integers at most 1000; there is no caller-supplied chain-verification override or persisted cache. Historical descriptor/provenance parameters remain unavailable for record assignment in this phase and reject non-null caller values. It reports linked-event scope, complete chain/head envelope authentication, version, confirmed/candidate field coverage and unavailable original protected values independently. A verified chain prefix is insufficient. Scalar head observations before and after the complete walk must agree; concurrent legitimate advancement returns unavailable EVIDENCE_CHANGED_DURING_READ, never a false integrity failure. No row locks or transaction mutation are used. Excessive or unavailable chain evidence produces unavailable completeness. No autoflush, integrity-status mutation, signature repair or audit emission is allowed.

Version 1 is not a per-record emitter identifier. Explicit exact-source descriptor and independently established emitter provenance are needed before confirmed field coverage. The deployed eleven-field payload cannot be replaced by the retired eight-field verifier registry. Original creation status cannot be supplied from today's cursor or guessed values. Even authenticated envelope/chain evidence never returns `VerifiedCreationEvidence`, establishes unsigned facts, or overrides canonical §6.2. Diagnostic observations remain separate from INV-ARC-016's four canonical lineage states. Current v2/v3 payload verification is unchanged.

### 6.2B Immutable reversal linkage coverage

DOM-LED-001 §VII.0 and FEAT-LED-002 §VII.2/4 require an immutable new reversal effect containing original-effect and correlation linkage; originals are not modified. ORM/PostgreSQL guards freeze the retained historical `reversal_transaction_id` after INSERT. It is not an authoritative monetary or posting input and is not newly added to any signed payload. Ledger audit versions 2 and 3 keep their exact original sixteen- and nineteen-field protected registries; historical signatures, envelopes and audit coverage are unchanged. The new reversal effect receives its normal current lawful creation lineage. Audit records may describe the new reversal's ID without mutating the original row.

### 6.2C Bounded batch creation-evidence query

Operations owns `verified_creation_evidences(items, class_id, *, required_fields=(), max_chain_events, max_rows)`, the batch form of §6.2 for FEATs that must prove many records in one class. `items` are `(table, row)` pairs. It returns an immutable `CreationEvidenceBatch` holding one §6.2 result per item, in request order, plus a `chain_status` (`COMPLETE`, `UNAVAILABLE` or `INVALID`) and a reason. Reuse is confined to the single invocation: the complete class chain is walked and authenticated once, and every item then receives every row-specific §6.2 check (scoped pointer, INSERT linkage, token and signature version, exact linked-version field coverage including `required_fields`, current protected payload digest) against that walk. A `None` entry under `COMPLETE` is a row-specific proof failure and grants no authority.

Both budgets are server-owned ceilings (`CREATION_PROOF_MAX_CHAIN_EVENTS`, `CREATION_PROOF_MAX_ROWS`); callers may lower them, never raise them, and invalid budgets are rejected before any read. A chain or row count beyond its budget returns every entry unavailable; a verified chain prefix is never treated as a complete chain. The chain head is read as an independent scalar snapshot before and after the walk, never from a cached mutable ORM row. Disagreement returns unavailable `EVIDENCE_CHANGED_DURING_READ`; a missing head, missing signing key or infrastructure failure returns unavailable; a malformed head, continuity break, HMAC mismatch or head/walk disagreement returns `INVALID`. In every non-`COMPLETE` outcome all entries are unavailable. There is no persisted proof cache, mutable verification flag, caller-supplied verification result or bypass; the query runs without autoflush, locks or writes, so previews stay pure and commands keep their atomicity and existing integrity denials. The single-row §6.2 query is unchanged. FEAT-PROD-005/003/006 reconstruction and Ledger reversal-input coordination compose this query in place of one §6.2 call per record.

### 6.3 Nightly Verification Flow

```
scheduler triggers run_audit_invariant_check_job() at 03:00 UTC
  → run_full_invariant_check()
      → load all chain scopes from chain_heads
      → for each scope: verify_chain(scope, limit=1000)
          → walk AuditEvent rows ordered by sequence_number
          → check previous_hash continuity
          → check sequence gaps
          → recompute event_hash (with UTC normalization)
          → compare to stored event_hash
          → return VerificationResult(state, failure_type, ...)
  → update_integrity_status(results) under SystemAuditAuthority
      → write IntegrityStatus row
      → set degraded_since on first-failure transition
      → clear degraded_since on recovery
```

---

## 7. Lineage State Taxonomy (Operational Semantics)

This taxonomy is defined as canonical in `INV-ARC-016`. The operational semantics for this domain are:

| State | Detection Condition | `IntegrityStatus` Effect |
|---|---|---|
| `VERIFIED` | Chain continuous; HMAC valid; payload digest matches | `passing=True` |
| `UNVERIFIED` | `lineage_event_id IS NULL` | No effect (coverage gap, not a failure) |
| `INVALID` | Chain broken, HMAC mismatch, or payload mismatch | `passing=False`; `degraded_since` set |
| `DEGRADED` | Verifier infrastructure error | `passing=False`; `degraded_since` set; `failure_type=VERIFIER_ERROR` |

---

## 8. Edge Case Decisions

1. **`lineage_token` is a pointer, not proof.** `lineage_token` (copy of `AuditEvent.hmac_signature`) enables a fast "row was touched by the audit system" pre-check only. Canonical proof of lawfulness requires both payload digest match and a continuous chain walk.

2. **`UNVERIFIED` is not `INVALID`.** Rows with `lineage_event_id IS NULL` predate lineage rollout. Operators shall track coverage toward zero; the verifier shall not treat them as incidents.

3. **Per-class lazy genesis.** A `ChainHead` for `class:{class_id}` is created on first emit for that class. The `ChainHead` for `"system"` may be seeded at bootstrap.

4. **`SystemAuditAuthority` is not a FEAT.** It carries no business actor fields and shall not be used inside business mutation paths. Its sole permitted uses are genesis bootstrap, nightly verifier writes, and `IntegrityStatus` updates.

5. **`SystemAuditAuthority` thread-local ownership.** The `_system_audit_ctx` thread-local lives in `app/feats/base.py` to avoid circular imports. `app/services/audit_service.py` accesses it via late import.

6. **Sequence gaps are detectable deletions.** If an `AuditEvent` row is deleted from a chain, the verifier detects a `SEQUENCE_GAP` at the missing sequence number. This is an `INVALID` condition.

7. **Payload digest mismatch is a tampered row.** If a protected row's current field values do not hash to the `payload_digest` on its linked `AuditEvent`, the row was mutated outside the canonical write path.

8. Constitutional economic policy lineage is the owning domains' own append-only tables (`DOM-CLASS-003` §V). A table among them that §5.4 registers is subject to the same lawful-lineage verification requirements as monetary truth. (The retired class-wide lineage tables are no longer part of this list.)

9. **UTC normalization is mandatory for HMAC recomputation.** `emit_audit_event()` computes the event hash using `datetime.now(timezone.utc).isoformat()` which yields `+00:00`. PostgreSQL/SQLAlchemy may return stored `TIMESTAMPTZ` values in the local session timezone. The verifier shall normalize all retrieved datetimes to UTC before recomputation.

10. **No HMAC reuse across scopes.** The chain scope is a field in the HMAC message, ensuring that an event from one class chain cannot be replayed into another.

11. **One emit per row creation.** `audit_protected()` shall be called exactly once per protected row creation, immediately after `flush()` and before the owning transaction commits. Re-invocations for the same row without a state change are prohibited.

12. **`lineage_version` tracks schema evolution.** When the HMAC schema or canonical payload format changes, `signature_version` and `signer_key_id` enable the verifier to apply the correct recomputation logic per event.

13. **`IntegrityStatus.degraded_since` is set on first failure.** If a new `IntegrityStatus` row is created in a failing state, `degraded_since` shall be set to the current UTC time. If an existing passing row transitions to failing, `degraded_since` shall be set. If the row recovers, `degraded_since` shall be cleared to `None`.

---

## 9. Amendment

Version 1.10 (2026-10-04) adds §6.2C's bounded batch form of the §6.2 creation-evidence query, so a batch walks each unchanged class chain once instead of once per record. Supersedes no proof requirement: every row-specific §6.2 check, the complete-chain requirement and fail-closed unavailability are retained, and no proof cache, verification flag or bypass is authorized.

Version 1.9 (2026-10-03) clarifies immutable exact-reversal linkage and frozen retained original pointers under §6.2B. Supersedes no signed registry or historical evidence.


Version 1.8 (2026-10-03) incorporates SPEC-PROD-002 §VII for FEAT-PROD-005/003 historical reconstruction observations alongside FEAT-PROD-006. Supersedes diagnostic-only consumer restriction, without changing canonical lineage taxonomy, verifier/signature versions, protected fields or new-write requirements. No original linkage/status replacement, status guess or historical signing is authorized.


Version 1.7 (2026-10-03) adds §6.2A's bounded historical envelope/coverage diagnostic query only. Supersedes no canonical payload registry, lineage taxonomy, typed creation proof or lawful write protocol.


Version 1.3 (2026-10-03) supersedes 1.2's incomplete protected registry for interval and payroll correction execution. Authority derives from `INV-CORE-000` §III.1–6, `INV-ARC-006` §V, `INV-ARC-016` §V–VI/IX, and `INV-ARC-021` §V/VII. Operations owns emission/verification only; eligibility and monetary conclusions remain owned by their respective domains. No runtime registry change is included.


Revisions must preserve the append-only guarantee for `audit_events`, the HMAC chain integrity algorithm, the `UNVERIFIED ≠ INVALID` distinction, and the two-path lawful write model. Any change to the canonical payload format or HMAC message structure shall increment `signature_version`.

Audit metadata must not copy authentication principal IDs, including a teacher alias.
The removed `teacher_id` was outside the signed event/context inputs; removing that
column preserves accepted chain hashes. Class attribution remains `seat_id` and `class_id`.

Version 1.4 (2026-10-03) supersedes the unqualified payroll UPDATE prohibition only for complete, one-time linkage initialization in the creating transaction (§6.1). It requires immutable business fields before INSERT, permanent linkage immutability after commit, deferred creation enforcement, and atomic audit failure rollback. Historical records remain untouched.

Version 1.6 (2026-10-03) registers nineteen-field Ledger signature version 3 while preserving exact sixteen-field version-2 verification, and applies the protected invalidation triple-linkage creation protocol. It supersedes future-only compensation registration and incomplete invalidation linkage without reinterpreting historical signatures.

Version 1.5 (2026-10-03) registers the sixteen implemented immutable Ledger creation fields under signature version 2; the three prospective compensation fields require their own later registered version before correction implementation. It supersedes stored-status payload registration for new Ledger events without reinterpreting historical version 1 signatures.
