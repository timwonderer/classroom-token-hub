# FEAT-STOR-007: Insurance Coverage Renewal

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-STOR-007 | 1.0 | 2026-09-24 | N/A | Normative |

## I. Purpose

Coordinate the recurring premium lifecycle of an insurance entitlement: assess each period's premium in advance, attempt automatic payment, and apply the policy's nonpayment behavior.

This FEAT is a coordinator. It owns no persistence. Every mutation it causes is performed by the owning domain's canonical command:

- bill-cycle succession and termination, and premium assessment and satisfaction — Obligations (`DOM-OBL-001`);
- premium payment — Ledger (`DOM-LED-001`), through the lawful obligation-satisfaction path;
- nonpayment expiry — Store and Entitlements (`DOM-STORE-001`, `FEAT-STOR-002`).

It introduces no insurance-specific recurrence, scheduling, or replay machinery. It uses `schedule_next_bill_cycle`, its command reservation, and the same advance-assessment rule rent uses (`DOM-OBL-001` §V.7).

## II. Authority

Store and Entitlements owns the insurance coverage lifecycle and its usability (`DOM-STORE-001` §VIII.E.1).

Obligations owns premium-obligation truth, the premium lineage, and the product-blind read of whether the lineage's required obligations are satisfied (`DOM-OBL-001` §VIII).

Policies owns the frozen terms of the purchased policy version: premium, cadence, bill preview interval, and nonpayment mode (`DOM-POL-001A` §V.E). They are resolved from the exact `policy_uuid` the entitlement and its cycles carry, never from the family's current row.

Ledger owns money movement.

## III. Required Context

- `class_id`
- the insurance `entitlement_id`; the premium lineage's `internal_ref` derives from it alone (`DOM-OBL-001` §II.B)
- the canonically resolved reference time (`INV-ARC-015` §VII)
- a command identity for each succession it requests (`DOM-OBL-001` §V.7)

## IV. Cadence

The purchase instant begins the first period. The purchase's class-local calendar date is the cadence anchor. Boundary `n` is `anchored_recurrence_boundary(anchor, cadence, n, overflow = roll_forward)` at class-local midnight (`SPEC-TIME-001` §IX.12); `WEEKLY` is seven class-local calendar days, `MONTHLY` rolls forward when the anchor day does not exist. Every boundary is derived from the anchor, never from the previous boundary.

## V. Advance Assessment and Automatic Payment

When the current cycle's assessment point arrives (`next_assessment_at − preview`, preview from that cycle's own `policy_uuid`), and the lineage is not terminated, the FEAT SHALL, in one transaction:

1. request succession for the next period through `schedule_next_bill_cycle`, with that period's boundaries from §IV;
2. assess that period's premium against the new cycle — the frozen per-period premium (`SPEC-ECON-003` §4.4.2), due at the new cycle's `cycle_boundary_at`;
3. attempt automatic satisfaction from the seat's available funds through the lawful satisfaction path.

If automatic satisfaction fails, the premium remains outstanding and the transaction still commits steps 1–2. The student may satisfy it manually at any later time, before or after its due boundary, through the ordinary obligation payment path. Whether a fee applies to the failed attempt is governed by `SPEC-ECON-003` §4.5.1.1, unchanged by this FEAT.

The FEAT SHALL NOT assess a premium for a period that begins after the lineage's termination.

## VI. Rollover

At a coverage boundary the previous period ends unconditionally. The FEAT performs no write to make the new period usable: usability is derived (`DOM-STORE-001` §VIII.E.1). A premium satisfied before the boundary yields continuous coverage; an unsatisfied premium leaves the new period gated until satisfaction, and satisfaction restores usability from that moment forward only.

## VII. Nonpayment

The purchased policy version's `nonpayment_mode` governs.

**`ACCUMULATE`.** The FEAT continues §V on cadence regardless of outstanding premiums. It never terminates the entitlement for nonpayment.

**`CANCEL_AFTER_X_DAYS`.** The nonpayment deadline is the coverage boundary at which the earliest outstanding required premium lapsed, plus `cancel_after_days` class-local calendar days. Later assessments do not reset it. §V continues until the deadline, so further premiums may be assessed while the delinquency is unresolved. When the deadline is reached and that premium is still unsatisfied, the FEAT SHALL, in one transaction:

1. record `EXPIRED` for the insurance entitlement with a nonpayment cause, effective at the deadline (`FEAT-STOR-002`);
2. terminate the premium lineage through the Obligations termination command, so that no later period is assessed.

It SHALL NOT void, reverse, waive, or forgive any assessed premium. Payment after termination settles the obligation and does not resurrect the entitlement.

## VIII. Idempotency and Replay

Succession replay is governed by `DOM-OBL-001` §V.7: each succession carries its own command identity, and a losing race is a conflict, never a replay and never a later successor. Assessment and satisfaction replay follow their own Obligations and Ledger contracts. Nonpayment expiry is idempotent on the entitlement: an entitlement already expired is not expired again, and a lineage already terminated is not terminated again.

## IX. Atomicity and Failure

Each unit in §V and §VII commits entirely or not at all, except that a failed automatic payment attempt is an expected outcome of §V, not a failure: the succession and assessment commit, and the premium stays outstanding.

A run that finds nothing due for an entitlement writes nothing.

## X. Prohibited Patterns

- persisting a cached `SUSPENDED`, `payment_current`, or similar authorization flag;
- inspecting obligation tables, or reconstructing payment status, instead of the Obligations read;
- deriving a boundary from a previous boundary, from a fixed day count for `MONTHLY`, or by clamping to month end;
- resolving premium, cadence, preview, or nonpayment terms from any policy row other than the exact `policy_uuid` the entitlement and its cycles carry;
- scaling the premium by the length of a period;
- restoring coverage retroactively for a gated interval;
- recording nonpayment termination as `REVOKED`, or voiding assessed premiums on termination;
- insurance-specific succession, scheduling, or replay machinery parallel to the Obligations commands.

## XI. Postconditions

- After an assessment point: exactly one successor cycle and one premium assessment exist for the next period, and a satisfaction exists if and only if automatic payment succeeded.
- After a boundary: the entitlement is usable if and only if Obligations reports its required premiums satisfied and it has not expired.
- After a nonpayment deadline under `CANCEL_AFTER_X_DAYS` with the triggering premium unsatisfied: the entitlement is `EXPIRED` with a nonpayment cause, the lineage is terminated, every previously assessed premium is still outstanding or satisfied as before, and no later premium is ever assessed.

## XII. Dependencies

- `DOM-STORE-001` §VIII.C, §VIII.E.1
- `DOM-OBL-001` §II.B, §V.7, §VIII, §IX
- `DOM-POL-001` §VII; `DOM-POL-001A` §V.E
- `SPEC-TIME-001` §IX.12–13
- `SPEC-ECON-003` §4.4.2, §4.5.1.1
- `FEAT-OBL-002` (bill-cycle succession)
- `FEAT-STOR-002` (entitlement expiry)
- `FEAT-STOR-003` (claims; eligibility at filing, per-period scope)

## XIII. Amendment

Revisions must remain consistent with `DOM-STORE-001`, `DOM-OBL-001`, `DOM-POL-001`, and `INV-ARC-015`, and SHALL NOT introduce persistence owned by this FEAT.
