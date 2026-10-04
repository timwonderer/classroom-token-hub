# SPEC-LED-001: Ledger Verification Proof Surfaces

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-LED-001 | 1.1 | 2026-10-03 | 1.0 | Normative |

## I. Purpose

Define the read-only Ledger proof surfaces consumed by Operations verification.
These surfaces expose Ledger-owned conclusions without transferring Ledger
reconstruction logic or authority to Operations.

## II. Scope and Authority

This specification is subordinate to `DOM-LED-001` and governs only Ledger
verification reads. It does not define verifier scheduling, Operations state
aggregation, external status publication, schema migrations, or runtime
implementation.

Operations MAY consume these results but MUST NOT reimplement Ledger
reconstruction SQL, group arbitrary Ledger rows, or infer Ledger invariants
independently.

## III. Common Contract

Every surface MUST:

- require canonical scope inputs before querying;
- be pure and read-only, with no settlement, repair, projection update, or
  lifecycle mutation;
- use canonical `ledger_transaction` history and Ledger-owned semantics;
- return bounded structured evidence, not ORM rows or unrestricted payloads;
- distinguish `PASS`, `FAIL`, and `UNAVAILABLE`;
- report `UNAVAILABLE` when required history, cursor, posting state, or proof
  inputs are missing or cannot be established;
- keep identifiers, amounts, and row-level diagnostics inside Ledger unless an
  explicitly authorized internal consumer requires them.

`FAIL` means the requested Ledger proposition was disproved. `UNAVAILABLE`
means Ledger could not lawfully establish the proposition. Neither may be
converted to `PASS` by a caller.

## IV. Proof Surfaces

### 4.1 `reconstruct_posted_balance`

```text
reconstruct_posted_balance(
    class_id,
    seat_id,
    account_type,
    through_posting_sequence?
)
```

The surface reconstructs the posted balance from canonical posted Ledger
history for exactly `(class_id, seat_id, account_type)`. It MUST NOT read or
depend on `ledger_balance_snapshot`.

When `through_posting_sequence` is supplied, the reconstruction includes every
canonical transaction in scope with `posting_sequence` less than or equal to
that boundary. The boundary MUST be a non-negative integer (excluding booleans)
established for that exact account scope. Missing or invalid boundaries produce
`UNAVAILABLE`. With no independent canonical boundary supplied or established,
the surface MUST return `UNAVAILABLE`; it MUST NOT infer admission from the
highest allocated sequence, a snapshot, wall-clock time, or transaction ID.
An explicit boundary proves the historical sum at that boundary; it does not
by itself prove that a projection asserts the same reconciliation boundary.

The internal result contains the reconstructed cents, boundary, evidence
completeness, and bounded diagnostic code. The Operations-facing result is a
bounded proof outcome and comparison metadata only; it does not expose seat
identifiers, transaction identifiers, or transaction-level amounts to external
adapters.

### 4.2 `reconstruct_available_balance`

```text
reconstruct_available_balance(
    class_id,
    seat_id,
    account_type,
    through_posting_sequence?
)
```

The surface reconstructs available balance from canonical Ledger history:

```text
posted balance through the explicit account reconciliation boundary
+ pending Ledger delta above that boundary in the same scope
```

It MUST NOT call `get_available_balance()` or any projection-based normal read,
and MUST NOT read `ledger_balance_snapshot` as an input to the reconstruction.
The pending inclusion and correction rules are Ledger-owned and must be applied
consistently with `DOM-LED-001`.

The boundary requirements and fail-closed defaults in §4.1 apply equally to
this surface. An omitted boundary cannot silently select zero or infer a cursor
from allocated sequences. Any scoped row whose required sequence or monetary
evidence is unavailable makes the reconstruction `UNAVAILABLE`; it MUST NOT
be silently omitted from a sum.

The result MUST identify whether both posted-history and pending-evidence
components were complete. Missing evidence produces `UNAVAILABLE`, not zero or
`PASS`.

### 4.3 `verify_transfer`

```text
verify_transfer(class_id, correlation_id, through_posting_sequences?)
```

The surface evaluates the transfer contract in `DOM-LED-001` for one
class-scoped transfer correlation. It MUST use `correlation_id` as the
canonical transfer-operation identity and MUST NOT use descriptions,
`original_transaction_id`, transaction IDs, or global aggregation to identify
the legs.

`through_posting_sequences` identifies independent canonical reconciliation
boundaries for both `checking` and `savings` in the transfer seat and class,
using exactly those two account keys.
Each boundary MUST be a non-negative integer excluding booleans. Missing or
invalid boundaries produce `UNAVAILABLE`; allocated sequence alone does not
establish admission, and the reconstruction MUST NOT obtain posting evidence
from snapshots or a projection-derived transaction property. Each leg must be
at or below its own account boundary to establish posting consistency.

The proof evaluates, without exposing row-level detail to external consumers:

- exactly two Ledger legs;
- one shared `class_id` and `seat_id`;
- one debit and one credit across permitted account types;
- equal absolute `amount_cents` and signed total zero;
- correlation non-reuse for another transfer pair;
- atomic creation and posting consistency.

The result MUST be `UNAVAILABLE` when the correlation, posting evidence, or
atomicity evidence cannot be established. A malformed or disproven transfer
contract is `FAIL`, not `UNAVAILABLE`.

## V. Evidence and Cost

These surfaces are safe for scheduled verification because they are read-only,
class-scoped, and do not trigger settlement. Reconstruction may be more
expensive than the normal projection read and may require indexed access to
canonical Ledger history. Physical indexes, caching, batching, and cadence are
implementation decisions outside this specification.

Ledger MAY retain richer internal diagnostics for operator investigation, but
the proof result consumed by Operations MUST remain bounded and must not contain
tenant detail, PII, credentials, raw query output, or arbitrary diagnostic
payloads.

## VI. Non-Goals

This specification does not:

- create a Ledger verifier runner;
- define DOM-OPS correctness-state mapping;
- define external status semantics;
- authorize writes to snapshots or transactions;
- replace the canonical Ledger transaction or balance contracts.

## VII. Dependencies

- `DOM-LED-001_LEDGER_DOMAIN.md`
- `DOM-OPS-001_OPERATIONS_DOMAIN.md` (consumer boundary only)
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`

## VIII. Change Notes

**1.1 (2026-10-03)** adds explicit account reconciliation boundaries to balance
reconstruction and transfer-proof signatures and supersedes implicit boundary resolution without
independent evidence. Missing or invalid boundaries and incomplete scoped
history remain unavailable. This specification authorizes no posting writes;
DOM-LED-001 §IX.1 and FEAT-LED-001 incorporate these proof requirements.
