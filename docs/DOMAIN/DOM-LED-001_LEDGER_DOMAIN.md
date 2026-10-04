# DOM-LED-001: Ledger Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-LED-001 | 2.10 | 2026-10-03 | 2.9 | Constitutional |

---

## I. Purpose

This document defines the Ledger domain as the absolute sovereign of monetary truth, transactional history, and balance derivation. It provides the mathematical proof of balance for all other domains and ensures the immutable integrity of the classroom economy.

## II. Scope

This domain governs the lifecycle of **money movement**, **transactional event logs**, and **balance derivation**.

**Ledger is domain-blind.** It possesses no knowledge of the economic meaning behind transactions (e.g., rent, payroll, or store items). It treats all financial events as abstract credits or debits.

This domain does not own:
- **Economic Context**: Owned by the domain requesting the transaction (e.g., Obligations, Attendance).
- **Class Scoping**: Ledger does not own `join_code`. Isolation is enforced explicitly via `class_id` plus seat-scoped anchors.
- **Solvency Policy**: Ledger does not decide if an overdraft is allowed; it only reports the balance. FEAT-LED-000 resolves intended ledger plans into resolved ledger plans when policy or recovery transforms are required before posting.

The Ledger posting sequence is the canonical ordering boundary for posted-ledger reconstruction. It is distinct from `effective_at`, `posted_at`, and persistence time.

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000` and `INV-CORE-001`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- [SPEC-LED-001](../SPEC/SPEC-LED-001_LEDGER_VERIFICATION_PROOF_SURFACES.md) §III–V — incorporated pure, bounded reconstruction proof; see §IX.1.

## V. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `ledger_transaction` (immutable financial event log)
- `ledger_balance_snapshot` (spendable balance cache)

No other domain may define fields or mutate these tables. Mutation is permitted only through the designated `ledger_service`.

## VI. State Classification

| State | Classification | Rationale |
| :--- | :--- | :--- |
| **Ledger Transaction** | Authoritative Event | The immutable, atomic unit of money movement. |
| **Transaction Status** | Derived State | `PENDING` / `POSTED` is derived from the reconciliation watermark, not stored on the row. |
| **Idempotency Lock** | System Guard | A scoped write constraint against duplicate intent. |
| **Posted Balance Snapshot** | Projection | An optimized view of spendable funds; re-derivable from events. |
| **Spendable Balance** | Derived State | The authoritative sum of all transactions included in the latest reconciliation boundary. |

## VII. Invariants

- **INV-LED-001: Class-Bound Transaction Scope**. All financial state shall be anchored to `class_id`, `target_seat_id`, and `actor_seat_id`. Isolation is not inferred from global seat uniqueness.
- **INV-LED-002: Immutable Facts**. Once inserted, a transaction row's protected fields are immutable. No later lifecycle patching is allowed. Immutability is a rule about mutation of a **surviving** class universe; see §VII.2 for its boundary against lawful lifecycle destruction.
- **INV-LED-003: Append-Only Corrections**. Authorized reversals and monetary corrections must be recorded as **new** transactions linked through immutable compensation provenance, `correlation_id`, and type, not by mutating the original row. VOID acts on grants, never on monetary transactions.
- **INV-LED-004: Reconciliation-Derived Posting**. `PENDING` and `POSTED` are reconciliation semantics, not stored transaction state.
- **INV-LED-005: Command-Scoped Idempotency**. Ledger idempotency belongs to
  command intent, not to an individual effect row. An accepted idempotent
  command reserves its `idempotency_key` within the canonical command namespace
  and records a replay fingerprint of the immutable command attributes required
  to establish replay equivalence. A replay with the same reservation identity
  MUST return the accepted command outcome only when its replay fingerprint
  matches; a mismatch MUST fail closed. The reservation remains permanent and
  MUST NOT be released by VOID, reversal, or any later correction.
- **INV-LED-006: Snapshot Fallback**. The `Posted Balance Snapshot` is a projection. If the snapshot is missing or inconsistent, the balance MUST be rebuildable from ledger history.
- **INV-LED-007: Canonical Posting Sequence**. Every accepted transaction receives one immutable `posting_sequence` allocated by the lawful Ledger effect-creation posting command before INSERT; reconciliation alone establishes admission to posted-ledger history. The sequence is monotonically increasing within one `class_id` and is unique within that class. It does not replace business or provenance timestamps.
- **INV-LED-008: Snapshot Reconciliation Cursor**. A balance snapshot records `reconciled_through_posting_sequence`, meaning that its posted balance has considered all canonical posted-ledger transactions for its `(class_id, seat_id, account_type)` scope whose `posting_sequence` is less than or equal to that cursor.
- **INV-LED-009: Atomic Seat Settlement**. A settlement affecting one `(class_id, seat_id)` MUST lock all applicable account snapshot rows in deterministic account order, reconcile them against one settlement boundary, assign posting sequences within the same transaction, and commit or roll back the complete seat-level settlement atomically.
- **INV-LED-015: Seat Balance Serialization**. Every operation that reads a seat's available balance to decide whether, or how much, to debit MUST acquire an exclusive lock on the scoped `seats` row before that read and hold it through the debit write. Every settlement for that seat MUST acquire the same lock. The lock order is deterministic: the `seats` row first, then the scoped `ClassEconomy` row, then pending transactions and balance snapshots. An available-balance read MUST evaluate its posted and pending terms within a single statement, so that no settlement commit can land between them. A credit that reads no balance does not need the seat lock. The seat row is thereby the single serialization point for a seat's money.
- **INV-LED-010: Atomic Multi-Row Integrity**. Any operation involving multiple entries (e.g., transfers) MUST be committed atomically.
- **INV-LED-011: Signed Magnitude**. Direction is defined strictly by sign: **Positive (+) = Credit**, **Negative (-) = Debit**.
- **INV-LED-012: Domain Blindness**. The `account_type` field classifies the target account and must not be used to encode business meaning (e.g., "RENT").
- **INV-LED-013: Reversal Uniqueness**. A transaction may be the target of at most **one** reversal transaction.
- **INV-LED-014: Transfer Correlation Identity**. An internal account transfer is one
  class-scoped operation identified by one `correlation_id`. It MUST contain exactly
  two `ledger_transaction` legs: one debit from the source account and one credit
  to the destination account, with equal absolute `amount_cents` values and a
  signed total of zero. The legs MUST share the same `class_id`, `seat_id`, and
  `correlation_id`, and MUST be created and committed atomically. A transfer
  `correlation_id` MUST NOT be reused to create another transfer pair. This
  invariant governs the current internal checking/savings transfer semantics;
  cross-seat transfers are not authorized by this contract.

### VII.1 Command Idempotency Semantics

The command-idempotency contract has three distinct layers:

1. **Reservation identity**: `(class_id, feat_code, idempotency_key)`. The
   `class_id` is the tenant/authority boundary, `feat_code` identifies the
   originating command family, and `idempotency_key` identifies the caller's
   command within that family. `type` and effect-level attributes MUST NOT
   expand this reservation namespace.
2. **Replay fingerprint**: the immutable command attributes required to prove
   that a retry is the same command, rather than a new command reusing an old
   key. Fingerprint attributes are compared on replay and are not uniqueness
   dimensions that make a mismatched replay lawful.
3. **Ledger effects**: one accepted reservation MAY produce one or more Ledger
   effect rows, provided all effects are produced by that command and committed
   atomically.

Every canonical Ledger command path MUST be retry-safe and MUST use a command
reservation unless an explicit Ledger contract identifies a genuine exception.
No exception may be inferred from an existing write path that happens not to
provide a key. Transfer execution is included in this coverage and MUST
provide the same command reservation identity to its atomic effects.

The physical enforcement representation—reservation table, command record, or
another structural mechanism—is intentionally deferred. The current
`ledger_transaction` uniqueness constraint is transitional evidence and does
not, by itself, define command-level idempotency.

### VII.1A Bounded Compensation Authority

Under `INV-CORE-000` §III.1,3–6, `INV-ARC-006` §V, `INV-ARC-009` §V, and `INV-ARC-016` §V, Ledger owns monetary compensation facts and exposes pure scoped queries for original credit, attributable recovered cents, and remaining recoverable cents. Ledger does not decide whether work was eligible or which work contributed to a payment. Originating FEATs supply a domain-authorized correction intent; Ledger accepts only its own authoritative monetary result.

For a positive original credit of `C` cents, let `R` be the sum of committed compensation amounts attributable to that original. Committed compensation includes accepted pending and posted effects, independent of reconciliation state. Ledger MUST enforce `0 <= R <= C`; a new recovery `D` MUST satisfy `0 <= D <= C - R`. Compensation linkage is immutable and class/target-seat scoped. Every partial/residual recovery and exact payroll reversal MUST carry the origin locator, intent locator and attributable cents. Ledger derives attributable recovery as the absolute signed debit magnitude applied to the original credited account; the compensation cents MUST equal that magnitude and cannot be caller-chosen bookkeeping independent of the effect. Funding legs and fees MUST carry zero attributable cents. Missing or inconsistent lineage fails closed. Ledger exposes the complete scoped original/recovery candidate requirements. The originating FEAT obtains Operations' immutable verified creation evidence for every candidate and maps it to Ledger's neutral `LedgerCreationEvidence` input: exact table/row/class locators, linkage event/token/version, covered protected field names and immutable protected values. Ledger matches these inputs to its own current locked source rows and required version-specific coverage; missing, extra, mismatched or incomplete candidates deny recovery. This server-side evidence cannot be supplied by a client or replaced by a verification boolean. No Ledger-to-Operations call or internal class/registry dependency is authorized. An exact whole-transaction reversal is permitted only when `R = 0`, and contributes `C` to `R`. A partial or residual correction is a separately authorized fresh debit, never `REVERSAL` or `VOID`. A residual correction contributes exactly `C - R`. Once `R = C`, later eligibility invalidation has no additional monetary recovery. Transfer debit/credit legs and fees contribute zero to `R`; account funding is not recovery from the original credit. Zero recovery does not create a zero-amount correction row.

All settlement, correction and full-reversal commands for the seat serialize through §VII INV-LED-015. Acquire the scoped seat lock first, then ClassEconomy, then the original Ledger transaction lock when compensation is involved, then pending transactions and snapshots in their existing deterministic order. An originating payroll settlement also acquires the seat lock before evaluating settlement eligibility, although it is a credit; its FEAT re-evaluates owning-domain evidence within that boundary. Check the cap and append all recovery effects inside the same transaction; previews cannot reserve recovery. Different command keys do not permit double recovery for the same correction intent. Ledger structurally enforces unique `(class_id, target_seat_id, compensation_origin_locator, correction_intent_locator)` recovery intent identity, independently of command reservations.

`SPEC-LED-002` v1.2 §§III–VIII and its version-4 effect-plan/business-intent serializer amendment are explicitly incorporated for permanent command reservations and effect linkage. The mathematical compensation constraints here are Ledger-owned; any interval allocation method is supplied by its owning domain and coordinated only by a FEAT under `INV-ARC-021` §V, VII. No new DOM-to-DOM dependency or FK to another domain's internal table is authorized.

### VII.2 Immutability Scope and Lifecycle Destruction

Ledger immutability applies to financial state **within a surviving class
universe**. Ledger rows owned by an existing seat MUST NOT be rewritten or
selectively deleted. Lawful seat deletion destroys the ledger state owned by
that seat as part of removing that actor from the class universe. Lawful class
destruction removes the entire class-scoped ledger universe. Cascade deletion
performed as part of lawful lifecycle destruction is **not** a mutation of
surviving financial history.

The distinction is between mutating a universe that continues to exist and
destroying an entity from that universe. While a seat exists, its ledger
contribution is part of the economic truth of its `class_id`, and editing or
removing any part of it falsifies a reconciliation that other rows still
depend on. When the seat is destroyed, the actor and every economic effect
attributable to that actor cease together. There is never a lawful state in
which the seat is gone but the seat's money remains.

**Enforcement consequence.** INV-LED-002 is enforced against `UPDATE`, and
that is its correct and complete scope. A general prohibition on `DELETE` of
`ledger_transaction` MUST NOT be installed, because it would assert the
inverse rule — that ledger history must outlive the entity whose existence
gives it meaning — and would abort lawful actor removal.

**Implementation note.** `ledger_transaction.actor_seat_id` and
`target_seat_id` are **provenance and participation references**, not
economic ownership; economic ownership is carried by `seat_id`. A teacher seat
may therefore appear as `actor_seat_id` on rows owned by student seats. This
does not create a partial-destruction hazard, because deletion of a teacher
seat while its class survives is not a valid runtime state: class ownership
cascades from the teacher principal, class destruction cascades to all seats
and their ledger rows, and the lawful seat-deletion paths accept student seats
only. Teacher-attributed rows can therefore be reached by cascade only when
the entire class universe is already being destroyed, at which point no
surviving student economy exists whose reconciliation could be harmed.

## VIII. Schema Contract

### 1. `ledger_transaction`

The canonical, immutable record of financial intent and execution.

- `id` (PK)
- `seat_id` (legacy compatibility anchor; retained until a separate column-removal pass)
- `target_seat_id` (FK to seats)
- `actor_seat_id` (FK to seats)
- `class_id` (FK to classes.class_id)
- `mechanism` (Enum: `SELF`, `TEACHER`, `SYSTEM`)
- `amount_cents` (Integer; Signed)
- `timestamp` (Timestamp; UTC)
- `account_type` (String or Enum; canonical account target)
- `description` (Text)
- `correlation_id` (UUID; Required)
- `feat_code` (Text; Required)
- `idempotency_key` (String; Command reservation key; required for canonical
  idempotent command paths)
- `policy_id` (UUID; Frozen policy reference when applicable)
- `type` (Text; Required; `payroll_correction` identifies authorized fresh interval/residual payroll recovery, distinct from exact `REVERSAL`)
- `compensation_origin_locator` (Nullable String(128), opaque Ledger public locator identifying the original transaction; resolved only by Ledger within the same class/target-seat scope)
- `compensation_amount_cents` (Integer; historical rows may remain NULL; new effects explicitly record nonnegative attributable recovered cents, zero for non-recovery effects including funding-transfer legs; no historical/default backfill)
- `correction_intent_locator` (Nullable String(128), opaque originating-command intent locator; cannot reference or enforce another domain's internal table)
- `lineage_event_id` (FK to audit_events.id; nullable only for pre-rollout rows)
- `lineage_token` (Text)
- `lineage_version` (Integer)

### 1.1 Posting Sequence

- `posting_sequence` (Integer; required for canonical posted transactions; immutable)

`posting_sequence` is allocated by the lawful Ledger effect-creation command, under the class sequence-allocation lock, before INSERT and the creation audit signature. Reservation linkage, command key, initiating FEAT, and every protected business field are likewise fixed before INSERT. Settlement does not attach or replace this sequence or rewrite the initiating FEAT. It is monotonically increasing and unique within `class_id`. It is not derived from `id`, `timestamp`, `effective_at`, or `posted_at`, and it does not replace any of those fields.

`posted_at` may be initialized once by the lawful settlement command as an informational UTC settlement receipt. It is not a protected monetary input, a status flag, or an independent proof boundary; no reader may derive standing from its presence. It never changes signed fields or requires a replacement creation signature.

PENDING/POSTED is determined for `(class_id, seat_id, account_type)` by comparing this immutable sequence with that exact account scope's reconciliation cursor. A missing account cursor means the effect has not been reconciled. Sequence allocation alone does not prove posting. Settlement advances scoped snapshot balances/cursors atomically and may initialize the informational receipt described above. It SHALL NOT skip an earlier unreconciled effect in the same account scope, patch transaction status, or refresh its creation signature.

### 2. `ledger_balance_snapshot`

An optimization for rapid solvency checks.

- composite identity `(class_id, seat_id, account_type)`
- `class_id` (FK to classes.class_id)
- `seat_id` (FK to seats.id)
- `account_type` (Enum; checking or savings)
- `posted_balance_cents` (Integer; projection of canonical posted history)
- `reconciled_through_posting_sequence` (Integer; exact reconstruction cursor)
- `last_settlement_at` (Timestamp)
- `updated_at` (Timestamp)

The canonical posted-balance assertion is:

```text
posted_balance_cents
= SUM(amount_cents)
  for canonical posted ledger transactions
  matching (class_id, seat_id, account_type)
  with posting_sequence <= reconciled_through_posting_sequence
```

The inclusion and exclusion rules for posted, void, reversal, and other transaction semantics remain those defined by the Ledger transaction lifecycle and correction invariants. The snapshot does not become monetary authority by storing this projection.

## IX. Derived / Cross-Domain Rules

- **Solvency Check**: Any domain requiring a "solvency check" (e.g., Store) must query the `Spendable Balance`. Ledger provides the truth; the caller decides if the amount is sufficient.
- **Pending Logic**: `PENDING` totals are derived on-demand from the transaction log for UI display. They are never stored on the transaction row.
- **Available Balance**: Available balance is the posted balance projection plus the pending non-void Ledger delta for the same `(class_id, seat_id, account_type)` scope.
- **Reversal Chaining**: Chained reversals are prohibited. Corrections of corrections shall be handled as fresh transactions, not updates to prior rows.



### IX.1 Incorporated Independent Proof Boundary

SPEC-LED-001 §III–V governs Ledger's independent reconstruction queries. With an explicitly supplied canonical `through_posting_sequence`, reconstruct scoped cents from immutable Ledger rows through that boundary without reading snapshots. If no independent reconciliation boundary can be established when the caller omits it, return UNAVAILABLE; do not infer posting from the highest allocated sequence, a transaction ID, wall-clock time, or a snapshot. An explicit boundary proves the sum at that requested boundary, not that a projection currently asserts it. Historical rows lacking required sequence, reservation, or version-specific protected evidence remain unavailable for strict monetary proof. No signatures or historical monetary facts are rewritten.

### IX.2 Pure historical monetary assessment

Ledger exposes `get_historical_payroll_credit_records(*, ctx, class_id, target_seat_id, limit=1000)` to provide scoped bounded source records for FEAT-to-Operations composition only; it does not provide an unscoped table read or resolve business membership. Ledger owns `assess_historical_payroll_money(*, ctx, class_id, target_seat_id, business_input, records, audit_observations=(), creation_evidence=())`: a pure bounded query through FEAT-PROD-006 that resolves uniquely scoped credit locators, compares original recorded monetary amounts with explicit original-rule replay inputs, identifies unsupported compensation evidence and reports current strict proof eligibility separately. Business inputs and audit observations are immutable FEAT-supplied data, never cross-domain calls or verification booleans. This domain incorporates [SPEC-PROD-002](../SPEC/SPEC-PROD-002_HISTORICAL_ATTENDANCE_PROOF_ASSESSMENT.md) §V–VIII for diagnostic arithmetic/monetary boundaries only. Preserve exact historical arithmetic order; no current price substitution, invented allocation, persisted earnings, default-zero compensation or signature-version override is authorized. Diagnostic v1 coverage never satisfies §VII.1A or §IX.1. Existing v2/v3 proof and recovery APIs remain unchanged.

### IX.3 Conditional Historical Attribution Read Contract

Ledger incorporates SPEC-PROD-001 §VI.1 and SPEC-PROD-002 §VI.1 only for its owned future pure original-credit identity, exact original monetary replay and historical attribution calculation through FEAT-PROD-006. The FEAT supplies PROD-owned proven whole-pair share inputs, Policies-owned original setting evidence and Operations-owned canonical evidence as immutable scoped objects. Ledger must not pair attendance, select settings, verify another domain's internals or accept a client boolean as proof. No DOM-to-DOM dependency is created.

For independently proven original whole-pair shares, preserve exact original pricing descriptor/order/precision/quantization and derive historical attribution version 1 by rational largest remainder with canonical close-time/open-ID/close-ID ties. Each share's allocated cents equals its original quantized cents; shares sum to the uniquely identified original payroll credit. These are newly derived read results, never historically recorded allocations. Inconsistent cents or ambiguous original credit fail closed. Pending credit cannot supply posted-credit proof. This contract enables no new runtime API or integration. A positive business proof or allocation calculation neither satisfies §VII.1A/§IX.1 nor proves zero compensation; original lawful creation, posting and complete compensation gates remain unchanged. Historical v1 gaps remain unavailable.

## X. Change Notes

**2.10 (2026-10-03)** incorporates conditional historical attribution read authority (§IX.3), preserving original arithmetic and all strict monetary proof gates. Supersedes no execution or signature rule; no runtime change is claimed.

**2.9 (2026-10-03)** adds §IX.2's historical read diagnostics; supersedes no execution-proof or compensation-cap rule. Read agreement is not monetary authorization.


**2.6 (2026-10-03)** supersedes 2.5 for append-only correction vocabulary, bounded compensation linkage and serialization. Incorporates permanent command reservations explicitly; retains domain blindness and lawful lifecycle destruction. This is documentation authority for later implementation, not a schema migration.

**2.8 (2026-10-03)** registers the three implemented compensation fields in immutable nineteen-field creation payloads while retaining exact version-2 proof for its original sixteen fields. Historical unknown compensation evidence cannot be converted to zero.

**2.7 (2026-10-03)** specifies immutable posting-sequence allocation at effect creation and cursor-only reconciliation. Supersedes lifecycle assignment of signed fields; explicitly incorporates SPEC-LED-001 with fail-closed independent boundary defaults.

## XI. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
