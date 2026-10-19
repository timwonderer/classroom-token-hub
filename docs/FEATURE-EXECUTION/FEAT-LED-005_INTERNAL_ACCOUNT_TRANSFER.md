# FEAT-LED-005: Internal Account Transfer

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-LED-005 | 1.3 | 2026-10-18 | 1.2 | Normative |

---

> [!IMPORTANT]
> **v1.3 (2026-10-18).** Both halves of the 2026-10-18 work landed independently, on separate PRs, and are recorded together here. The route/registry cutover (PR #1599): `FEAT-LED-005` is registered in `app/feats/base.py`'s FEAT registry, and `app/routes/student.py`'s internal-transfer route now opens `FEATContext("FEAT-LED-005", ...)`. A structural guard (`tests/guards/feat_led_000_route_usage.py`, `tests/test_feat_led_000_route_guard.py`) fails the build if any `app/routes/` file reopens `FEAT-LED-000`. §VIII's invariants now describe live runtime behavior, not a target state. Separately, §IX's DB `CHECK` constraint has landed (migration `a4d7e9c2f1b6`); its write-time casing validator has not — see §IX below.
>
> **v1.2 (2026-10-18).** Recorded the two halves separately while only one had landed. Superseded by v1.3 above, which records both as landed.
>
> **v1.1 (2026-10-18).** This contract is prospective: it establishes the design this FEAT must satisfy once a later PR performs the runtime cutover. As of this revision, `app/routes/student.py`'s internal-transfer route still opens `FEATContext("FEAT-LED-000")`, and `FEAT-LED-005` is not yet registered in `app/feats/base.py`'s FEAT registry. Attempting to open `FEATContext("FEAT-LED-005")` today raises `FEATContextError` (unregistered FEAT). §VIII's invariants describe the target state this FEAT's cutover PR must achieve, not current runtime behavior. Also restructures this document to the required section order (`SOP-DOC-000` §VIII): Purpose, Scope, Authority Level, Dependencies, content, Amendment — v1.0 omitted Scope and Authority Level and ended with Change Notes instead of Amendment.

## I. Purpose

This FEAT is the top-level orchestration identity for a student's own voluntary checking/savings transfer.

It exists to give the internal-transfer route a real, dedicated `FEATContext` of its own. Before this FEAT, `app/routes/student.py` opened its transfer `FEATContext` under `FEAT-LED-000` — the canonical monetary-resolution **workflow** identity, which `FEAT-LED-000` §0 (Execution-model reconciliation) and its v0.6 Change Note explicitly disclaim as ever having been a route-level orchestration identity. `FEAT-LED-005` corrects that: following its cutover PR (#1599), it is the one live top-level `FEATContext` an internal transfer actually runs under.

This FEAT does not define transfer *mechanics* — the exact two-leg shape, correlation identity, and atomicity are `DOM-LED-001` INV-LED-014's, enforced by the Ledger-owned `build_transfer_effect_pair` primitive this FEAT composes. This FEAT defines the orchestration boundary around that primitive: who may invoke it, under what context, and what it does and does not touch.

## II. Scope

The internal checking/savings transfer route for a single authenticated student seat, within one class. This FEAT governs only the orchestration boundary (context establishment, `mechanism` supply, invocation of the transfer primitive) — not the transfer-effect shape, balance derivation, or reservation semantics, all of which `DOM-LED-001` and `FEAT-LED-001` own. Cross-seat transfers are out of scope and are not authorized by this contract or by `DOM-LED-001` INV-LED-014.

## III. Authority Level

Normative; subordinate to `INV-CORE-000`, `FEAT-CORE-000` §II–V (one atomic FEAT context per top-level orchestration), and `DOM-LED-001` (INV-LED-014, INV-LED-016), which this FEAT composes but does not redefine.

## IV. Dependencies

- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md` (INV-LED-014, INV-LED-016, INV-LED-017)
- `docs/FEATURE-EXECUTION/FEAT-LED-000_CANONICAL_MONETARY_RESOLUTION_WORKFLOW.md` (§XI.5, own-account transfer funding rule; v0.6 disclaims this FEAT's prior misuse as a route identity)
- `docs/FEATURE-EXECUTION/FEAT-LED-001_POST_LEDGER_TRANSACTION.md`

## V. Authority

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

## VI. Required Context

Required canonical context:

- `class_id`
- `seat_id` (acting and target are the same seat — an internal transfer never moves money between seats)
- `from_account`, `to_account` — distinct, each `checking` or `savings`
- `amount` — strictly positive
- `correlation_id`
- `idempotency_key`

No optional context. An internal transfer carries no business-specific metadata beyond the two account legs and the amount.

## VII. Orchestration Logic

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

## VIII. Invariants

These describe live runtime behavior as of v1.2; see the v1.2 note above.

1. An internal transfer's two legs share exactly one `correlation_id` and are created and committed atomically (`DOM-LED-001` INV-LED-014).
2. `mechanism = SELF` on both legs — this is always a student's own voluntary act; this FEAT supplies that value explicitly, never inferring it (`DOM-LED-001` INV-LED-016).
3. An internal transfer never crosses seats: `target_seat_id == actor_seat_id == seat_id` for both legs.
4. No protection transfer, fee, or obligation is evaluated or created by this FEAT.
5. This FEAT is the only lawful top-level `FEATContext` for the internal-transfer route; no code path may open `FEAT-LED-000` for this purpose (enforced by the structural guard named in the v1.2 note above).

## IX. Enforcement Scope for the DB `CHECK` Constraint and Write-Time Validator

The route/registry cutover above is independent of this section's enforcement. The DB `CHECK` constraint for `Transaction.type` (`DOM-LED-001` INV-LED-017) is deployed: migration `a4d7e9c2f1b6` adds `ck_ledger_transaction_type_closed_vocabulary`, enumerating INV-LED-017's full canonical/legacy table (`NULL` still permitted). It accepts either spelling of an aliased value (`Interest`/`interest`, `REVERSAL`/`reversal`, `Withdrawal`/`withdrawal`, `Deposit`/`deposit`) on a new row — it closes the set of lawful values, not the spelling a new row must use within that set.

The write-time casing validator — rejecting a legacy-cased value on a *new* row while the CHECK constraint continues to accept it on historical rows — remains undeployed. It is separate, later scope: it requires every current legacy-cased writer (`ledger_transfer_service.py`, `ledger_interest_service.py`, `ledger_recovery_service.py`, `ledger_correction_service.py`) to switch to canonical spelling, and every read/comparison site that still expects the legacy spelling — most critically `app/utils/transaction_idempotency.py`'s `IDEMPOTENT_TRANSACTION_TYPES` and `_AMOUNT_EXCLUDED_FROM_FINGERPRINT_TYPES`, whose silent mis-update would break interest-posting idempotency — to accept both spellings or be updated in lockstep. That PR's allow-list MUST still be drawn from INV-LED-017's canonical/legacy enumeration table, not re-derived from current writers.

## X. Amendment

Increment the version and effective date, identify superseded rules, and preserve the governing INV and DOM hierarchy. The §IX DB `CHECK` constraint and write-time casing validator are separate code work, tracked by their own not-yet-landed PR.

### Change Notes

**1.3 (2026-10-18)** reconciles v1.2's two independently-written histories (the route/registry cutover on #1599 and the DB `CHECK` constraint on #1600, each merged separately) into one record: both have landed; the write-time casing validator is the one piece of §IX still undeployed. No change to transfer mechanics, funding rules, or the effect-pair shape.

**1.2 (2026-10-18)** records that the cutover PR landed: `FEAT-LED-005` is registered and the internal-transfer route runs under it, guarded against regression back to `FEAT-LED-000`. §VIII and §X updated from prospective to live-runtime phrasing. No change to transfer mechanics, funding rules, or the effect-pair shape. §IX's DB `CHECK`/casing-validator enforcement remains undeployed.

**1.0 (2026-10-18)** establishes `FEAT-LED-005` as the dedicated top-level orchestration identity for the internal-transfer route, replacing its prior (incorrect) use of `FEAT-LED-000`. No change to transfer mechanics, funding rules, or the effect-pair shape — this is an identity/orchestration-boundary correction, not a behavior change.

**1.1 (2026-10-18)** restructures the document to `SOP-DOC-000` §VIII's required section order and corrects v1.0's description of this FEAT as a live context: it is prospective until its cutover PR registers it in `app/feats/base.py` and moves `app/routes/student.py`'s transfer route onto it. Adds §IX clarifying that the `type` enforcement mechanisms belong to that same later PR, not to this contract. No change to transfer mechanics, funding rules, or the effect-pair shape.

**1.2 (2026-10-18)** records that the DB `CHECK` constraint half of §IX has landed (migration `a4d7e9c2f1b6`), independently of this FEAT's own route/registry cutover (tracked separately; see the v1.1 note above for that status). The write-time casing validator remains the one item of §IX's original scope still undeployed. No change to transfer mechanics, funding rules, the effect-pair shape, or this FEAT's own orchestration status.
