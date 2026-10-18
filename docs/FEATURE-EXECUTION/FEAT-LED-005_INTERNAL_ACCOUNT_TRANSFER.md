# FEAT-LED-005: Internal Account Transfer

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-LED-005 | 1.0 | 2026-10-18 | — | Normative |

---

## I. Purpose

This FEAT is the top-level orchestration identity for a student's own voluntary checking/savings transfer.

It exists to give the internal-transfer route a real, dedicated `FEATContext` of its own. Before this FEAT, `app/routes/student.py` opened its transfer `FEATContext` under `FEAT-LED-000` — the canonical monetary-resolution **workflow** identity, which `FEAT-LED-000` §0 (Execution-model reconciliation) and its v0.6 Change Note explicitly disclaim as ever having been a route-level orchestration identity. `FEAT-LED-005` corrects that: it is the one live top-level `FEATContext` an internal transfer actually runs under.

This FEAT does not define transfer *mechanics* — the exact two-leg shape, correlation identity, and atomicity are `DOM-LED-001` INV-LED-014's, enforced by the Ledger-owned `build_transfer_effect_pair` primitive this FEAT composes. This FEAT defines the orchestration boundary around that primitive: who may invoke it, under what context, and what it does and does not touch.

---

## II. Authority

Ledger owns:

- the transfer-effect pair's shape (`DOM-LED-001` INV-LED-014)
- `build_transfer_effect_pair` — the pure constructor for the two-leg effect vector
- reservation, posting, and replay semantics (`create_reserved_effects`)

Identity owns:

- the acting seat's binding to the authenticated `user_id` (`resolve_canonical_context()`)

This FEAT owns:

- establishing the one atomic FEAT context an internal transfer executes under
- supplying `mechanism=SELF` (the student's own voluntary act, per `DOM-LED-001` INV-LED-016) to the builder
- invoking `create_reserved_effects` with the builder's output

This FEAT does not own monetary truth, balance derivation, or the transfer-effect shape itself; all of that is `DOM-LED-001`'s.

---

## III. Required Context

Required canonical context:

- `class_id`
- `seat_id` (acting and target are the same seat — an internal transfer never moves money between seats)
- `from_account`, `to_account` — distinct, each `checking` or `savings`
- `amount` — strictly positive
- `correlation_id`
- `idempotency_key`

No optional context. An internal transfer carries no business-specific metadata beyond the two account legs and the amount.

---

## IV. Orchestration Logic

### 1. Verification

1. Resolve the acting seat and class from canonical context (`resolve_canonical_context()`); never trust a caller-supplied `seat_id`/`class_id`.
2. Verify `from_account != to_account` and both are in `{checking, savings}`.
3. Verify `amount` is strictly positive.
4. Verify sufficient funds in `from_account` under the own-account transfer rule (`FEAT-LED-000` §XI.5: own-account transfers require sufficient source funds, use no protection, and incur no fee). This FEAT does not re-derive that rule; it is Ledger's balance-read authority that evaluates it.

### 2. Mutation

1. Construct the two-leg effect pair via `build_transfer_effect_pair(seat_id=..., class_id=..., target_seat_id=seat_id, actor_seat_id=seat_id, mechanism="self", correlation_id=..., amount=..., from_account=..., to_account=..., withdraw_description=..., deposit_description=...)`.
2. Post the pair via `create_reserved_effects(class_id=..., feat_code="FEAT-LED-005", idempotency_key=..., effects=pair)` — this FEAT does not hand-roll a reservation; it uses the same general-purpose reservation path every other multi-effect Ledger command uses.
3. Both legs commit atomically or neither does (`create_reserved_effects`'s existing atomicity guarantee; no new mechanism introduced here).

### 3. Derived state

This FEAT SHALL NOT persist a transfer "status," "history summary," or any projection over the two posted rows. The two `ledger_transaction` rows and their shared `correlation_id` are the entire durable record.

---

## V. Invariants

1. An internal transfer's two legs share exactly one `correlation_id` and are created and committed atomically (`DOM-LED-001` INV-LED-014).
2. `mechanism = SELF` on both legs — this is always a student's own voluntary act; this FEAT supplies that value explicitly, never inferring it (`DOM-LED-001` INV-LED-016).
3. An internal transfer never crosses seats: `target_seat_id == actor_seat_id == seat_id` for both legs.
4. No protection transfer, fee, or obligation is evaluated or created by this FEAT.
5. This FEAT is the only lawful top-level `FEATContext` for the internal-transfer route; no code path may open `FEAT-LED-000` for this purpose.

---

## VI. Dependencies

- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md` (INV-LED-014, INV-LED-016)
- `docs/FEATURE-EXECUTION/FEAT-LED-000_CANONICAL_MONETARY_RESOLUTION_WORKFLOW.md` (§XI.5, own-account transfer funding rule; v0.6 disclaims this FEAT's prior misuse as a route identity)
- `docs/FEATURE-EXECUTION/FEAT-LED-001_POST_LEDGER_TRANSACTION.md`

## VII. Change Notes

**1.0 (2026-10-18)** establishes `FEAT-LED-005` as the dedicated top-level orchestration identity for the internal-transfer route, replacing its prior (incorrect) use of `FEAT-LED-000`. No change to transfer mechanics, funding rules, or the effect-pair shape — this is an identity/orchestration-boundary correction, not a behavior change.
