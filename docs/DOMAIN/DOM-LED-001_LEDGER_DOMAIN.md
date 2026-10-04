# DOM-LED-001: Ledger Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-LED-001 | 2.13 | 2026-10-03 | 2.12 | Constitutional |

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
- **INV-LED-009: Atomic Seat Settlement**. A settlement affecting one `(class_id, seat_id)` MUST lock all applicable account snapshot rows in deterministic account order, reconcile them against one settlement boundary, advance scoped reconciliation cursors against existing immutable posting sequences within the same transaction, and commit or roll back the complete seat-level settlement atomically.
- **INV-LED-015: Seat Balance Serialization**. Every operation that reads a seat's available balance to decide whether, or how much, to debit MUST acquire an exclusive lock on the scoped `seats` row before that read and hold it through the debit write. Every settlement for that seat MUST acquire the same lock. The lock order is deterministic: the `seats` row first, then the scoped `ClassEconomy` row, then pending transactions and balance snapshots. An available-balance read MUST evaluate its posted and pending terms within a single statement, so that no settlement commit can land between them. A credit that reads no balance does not need the seat lock. The seat row is thereby the single serialization point for a seat's money.
- **INV-LED-010: Atomic Multi-Row Integrity**. Any operation involving multiple entries (e.g., transfers) MUST be committed atomically.
- **INV-LED-011: Signed Magnitude**. Direction is defined strictly by sign: **Positive (+) = Credit**, **Negative (-) = Debit**.
- **INV-LED-012: Domain Blindness**. The `account_type` field classifies the target account and must not be used to encode business meaning (e.g., "RENT").
- **INV-LED-013: Reversal Uniqueness**. A transaction may be the target of at most **one** reversal transaction. Ledger enforces this with a unique immutable reversal-origin locator, including accepted pending reversals. The original row is never updated to represent reversal; matching state is derived from the new reversal effect.
- **INV-LED-014: Transfer Correlation Identity**. An internal account transfer is one
  class-scoped operation identified by one `correlation_id`. It MUST contain exactly
  two `ledger_transaction` legs: one debit from the source account and one credit
  to the destination account, with equal absolute `amount_cents` values and a
  signed total of zero. The legs MUST share the same `class_id`, `seat_id`, and
  `correlation_id`, and MUST be created and committed atomically. A transfer
  `correlation_id` MUST NOT be reused to create another transfer pair. This
  invariant governs the current internal checking/savings transfer semantics;
  cross-seat transfers are not authorized by this contract.

Multi-seat balance-dependent commands MUST acquire every affected seat anchor in ascending seat-ID order before acquiring any ClassEconomy lock or applying monetary effects. Ledger owns `lock_ledger_seats(class_id, seat_ids)` for this scoped complete-set validation and locking; FEAT orchestration supplies the affected seats. This extends the seat-first order without changing immutable sequence allocation or settlement authority.

### VII.0 Immutable Reversal Linkage

Ledger owns `exact_reversal_query`, `get_exact_reversal`, and `has_exact_reversal`, pure queries over immutable `REVERSAL` effects. A reversal carries the original `correlation_id` and exact `original_transaction_id`; class, target/seat, account and exact opposite integer cents must agree with the locked original. Correlation alone may identify multiple operation effects, so it never replaces the exact original-effect locator. No reversal of a reversal is authorized. Ledger owns `replay_reserved_reversal`: an accepted retry reconstructs its complete immutable effect vector and verifies the stored-version reservation fingerprint against the requested actor, mechanism and compensation subtype before returning the original effect. It never reprices or resolves current balances for accepted replay.

Every exact reversal serializes seat → ClassEconomy → original effect before replay and eligibility, for original debits as well as credits. A partial unique index on `original_transaction_id` for `type = 'REVERSAL'` enforces one child across command keys; raw insertion guards validate the same scope/correlation/amount linkage. Paid-credit reversal also remains subject to §VII.1A's aggregate compensation cap. Full/partial/residual recovery races cannot create two reversals or exceed original credit.

Existing `reversal_transaction_id` values are retained frozen as historical material; the field cannot initialize or change after INSERT and is never the authoritative reversal state. New commands do not populate it. Historical reconstruction may inspect retained unsigned linkage only as an ambiguity/evidence candidate and must establish attribution from original immutable sources; the pointer alone proves no recovery. No data backfill, replacement signature, compatibility bridge or new cross-domain dependency is authorized. This clarifies existing INV-LED-002/003/013 and supersedes the implementation's write-once-pointer exception, not the immutable counter-entry rule.

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

For a positive original credit of `C` cents, let `R` be the sum of committed compensation amounts attributable to that original. Committed compensation includes accepted pending and posted effects, independent of reconciliation state. Ledger MUST enforce `0 <= R <= C`; a new recovery `D` MUST satisfy `0 <= D <= C - R`. Compensation linkage is immutable and class/target-seat scoped. Every partial/residual recovery and exact payroll reversal MUST carry the origin locator, intent locator and attributable cents. Ledger derives attributable recovery as the absolute signed debit magnitude applied to the original credited account; the compensation cents MUST equal that magnitude and cannot be caller-chosen bookkeeping independent of the effect. Funding legs and fees MUST carry zero attributable cents. Modern required lineage and actual integrity contradictions fail closed. Legacy reconstruction evidence follows §IX.3–4; missing post-rollout fields alone do not deny that distinct authority. Ledger exposes the complete scoped original/recovery candidate requirements. For modern version-2/3 sources the originating FEAT obtains Operations' immutable verified creation evidence for every candidate and maps it to Ledger's neutral `LedgerCreationEvidence` input: exact table/row/class locators, linkage event/token/version, covered protected field names and immutable protected values. Ledger matches these inputs to its own current locked source rows and required version-specific coverage; missing, extra, mismatched or incomplete candidates deny recovery. This server-side evidence cannot be supplied by a client or replaced by a verification boolean. No Ledger-to-Operations call or internal class/registry dependency is authorized. An exact whole-transaction reversal is permitted only when `R = 0`, and contributes `C` to `R`. A partial or residual correction is a separately authorized fresh debit, never `REVERSAL` or `VOID`. A residual correction contributes exactly `C - R`. Once `R = C`, later eligibility invalidation has no additional monetary recovery. Transfer debit/credit legs and fees contribute zero to `R`; account funding is not recovery from the original credit. Zero recovery does not create a zero-amount correction row.

All settlement, correction and full-reversal commands for the seat serialize through §VII INV-LED-015. Acquire the scoped seat lock first, then ClassEconomy, then the original Ledger transaction lock when compensation is involved, then pending transactions and snapshots in their existing deterministic order. An originating payroll settlement also acquires the seat lock before evaluating settlement eligibility, although it is a credit; its FEAT re-evaluates owning-domain evidence within that boundary. Check the cap and append all recovery effects inside the same transaction; previews cannot reserve recovery. Different command keys do not permit double recovery for the same correction intent. Ledger structurally enforces unique `(class_id, target_seat_id, compensation_origin_locator, correction_intent_locator)` recovery intent identity, independently of command reservations.

`SPEC-LED-002` v1.3 §§III–VIII and its version-5 effect-plan/business-intent serializer amendment are explicitly incorporated for permanent command reservations and effect linkage. The mathematical compensation constraints here are Ledger-owned; any interval allocation method is supplied by its owning domain and coordinated only by a FEAT under `INV-ARC-021` §V, VII. No new DOM-to-DOM dependency or FK to another domain's internal table is authorized.

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

Ledger exposes `get_historical_payroll_credit_records(*, ctx, class_id, target_seat_id, limit=1000)` to provide scoped bounded source records for FEAT-to-Operations composition only; it does not provide an unscoped table read or resolve business membership. Ledger owns `assess_historical_payroll_money(*, ctx, class_id, target_seat_id, business_input, records, audit_observations=(), creation_evidence=())`: a pure bounded query through FEAT-PROD-006 that resolves uniquely scoped credit locators, compares original recorded monetary amounts with explicit original-rule replay inputs, identifies unsupported compensation evidence and reports current strict proof eligibility separately. Business inputs and audit observations are immutable FEAT-supplied data, never cross-domain calls or verification booleans. This domain incorporates [SPEC-PROD-002](../SPEC/SPEC-PROD-002_HISTORICAL_ATTENDANCE_PROOF_ASSESSMENT.md) §V–VIII for diagnostic arithmetic/monetary boundaries only. Preserve exact historical arithmetic order; no current price substitution, invented allocation, persisted earnings, default-zero compensation or signature-version override is authorized. Diagnostic v1 coverage alone never supplies creation proof. The separate internally validated reconstruction contract in §IX.3–4 may establish legacy recovery authority under §VII.1A without upgrading original lineage. Modern v2/v3 verification remains exact and unchanged.

### IX.3 Historical Reconstruction Evidence

Ledger incorporates SPEC-PROD-001 §VI.1–2 and SPEC-PROD-002 §V–VIII for `validate_historical_settlement(*, ctx, graph, audit_observations, creation_evidence, business_creation_evidence=())`. FEAT supplies the immutable PROD graph, Operations observations and modern canonical creation evidence through owning-domain interfaces. Ledger re-reads complete bounded class/target monetary sources, validates original positive credit identity, exact original money and prior recovery, then returns immutable `ReconstructedSettlement(graph, origins, material, creation_evidence=())` with `ReconstructedOrigin` records. Its frozen modern creation-evidence set remains complete even when an original zero-cent run has no Ledger origin; recovery revalidation uses that exact modern proof without upgrading any old lineage. This is Ledger reconstruction evidence, a separate authority type from `LedgerCreationEvidence` and Operations `VerifiedCreationEvidence`; it is never a verification flag or client-supplied amount. A full reversal of another origin is excluded from this payment’s recovery candidates only when complete canonical creation evidence proves the version-3 signed compensation-origin locator, the counterpart credit, matching class/target/account/correlation, and exact opposite cents. Dangling or contradictory locators and unproven legacy attribution remain fail-closed; an unsigned original-effect ID alone is not proof of unrelatedness. No domain calls another domain.

Recognized original v1/legacy business representations may qualify by immutable source reconstruction, unique original credit binding and exact replay-paid aggregate equality despite unavailable retired status, original business linkage or newly introduced allocation/compensation fields. Class, target, actor, mechanism, account, original business identity and descriptor-supported original command/correlation linkage must agree uniquely; random route tokens, time proximity or amount equality alone are not identities. Unknown versions/shapes deny. Modern v2/v3 originals and all modern recovery/business effects retain full required version-specific creation evidence; malformed modern frozen records cannot enter legacy reconstruction. Mixed graphs enforce the appropriate evidence independently for each source.

Operations' authenticated complete original chain/envelope is required wherever an old link exists. Missing legacy linkage is recorded UNVERIFIED; irreproducible retired v1 payload coverage is recorded DEGRADED/VERIFIER_COVERAGE_UNAVAILABLE. Neither marks the original lawful or VERIFIED. Actual scope, authenticated payload, HMAC or chain contradictions deny INTEGRITY_FAILURE. No guessed status, digest search, replacement signature, fake creation proof or original-row amendment is permitted. Operational infrastructure unavailable for evidence or new lawful audit emission blocks the command.

For every original credit, money/cents agree exactly and its immutable positive sequence is admitted only through the exact scoped account reconciliation cursor. Pending original credits deny PAYROLL_PENDING without forced reconciliation. Original credit reservations are not backfilled or required merely because new commands use them. `allocate_reconstructed_shares` preserves recognized original order/context/truncation and quantization, then applies rational largest remainder over grouped exact microsecond weights. Per-share/window and original-credit conservation are mandatory; inconsistent totals or ambiguous inputs deny. Derived allocations are read results, never originally recorded cents.

### IX.4 Complete Graph Recovery and Atomic Execution

The reconstruction is complete over original fragment/remainder/top-up credits, zero-valued payroll boundaries, source shares and every relevant negative recovery. A recognized legacy reversal is attributable only when its original business-event reference, uniquely linked negative monetary counterpart, original full credit magnitude, class/target/account/actor/mechanism and pinned writer semantics agree. An unsigned old pointer or absent compensation field alone neither proves recovery nor proves zero. Count each recovery principal once. Ambiguous, duplicate or unattributed relevant legacy or modern recovery denies. Modern principals require v3 signed origin, intent and magnitude plus lawful correction business evidence for any interval attribution. Funding legs count zero. Both pending and posted accepted recovery count against each cap.

Every origin independently enforces §VII.1A: total attributable recovery never exceeds original credit. Full/residual recovery consumes the complete remainder; partial recovery requires unique interval attribution, otherwise paid interval recovery denies even if aggregate residual is independently calculable. Do not arbitrarily prorate prior recovery or cap an interval at an unknown remainder. A fully recovered or zero-cent contribution has no new debit but still requires complete reconstruction.

`resolve_reconstructed_recovery` derives one combined monetary plan under current authorized banking directives: aggregate positive debits in stable origin order, evaluate shortfall/protection once over the complete debit, and retain one principal/intent per origin. `apply_reconstructed_recovery` revalidates the complete reconstruction and all per-origin caps under target seat → ClassEconomy → stable original-credit → monetary-source locks, and applies all funding and recovery legs with one SPEC-LED-002 command reservation. No separate independently resolved plan may reuse starting balances. Exact full/residual/interval commands serialize together. Revalidate full preview evidence and balances; any changed evidence or failure rolls back everything. Current canonical creation protocol and all nineteen v3 fields protect new effects; no correction fee, obligation or deferred recovery occurs. No old signature, sequence, reservation or compensation linkage is rewritten.

## X. Change Notes

**2.12 (2026-10-03)** supersedes v2.9–2.11 blanket legacy creation-field and future-only recovery denial for independently validated immutable-source reconstruction. Adds distinct reconstruction evidence and complete graph recovery; modern strict proof, actual integrity rejection, per-origin caps and current new-effect audit remain binding. No INV or original monetary fact changes.


**2.11 (2026-10-03)** separately incorporates pure graph attribution (§IX.4) and per-origin conservation while preserving §IX.3 and every strict monetary gate. Supersedes graph future-only design scope, not runtime, signature or mutation authority.


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
