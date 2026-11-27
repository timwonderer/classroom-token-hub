# FEAT-IDEN-105: Private Class Confirmation and Aggregate Validation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-IDEN-105 | 1.4 | 2026-11-23 | 1.3 | Normative |

## I. Purpose

Validate private class confirmations and grant aggregate SATAR setup authority without
revealing individual proof validity or changing classroom participation.

## II. Scope

Class-scoped confirmation entry and principal-owned aggregate validation. Proven aggregate
success supersedes routine credential authority; recovery initiation does not.

## III. Authority Level

Normative FEAT contract subordinate to INV-CORE, INV-ARC-001/002/019 and DOM-IDEN-003 §IX.

## IV. Dependencies

- DOM-IDEN-003 §VII.A/IX and DOM-IDEN-005.
- INV-ARC-001/002/019, FEAT-CORE-000 and incorporated SPEC-SEC-001/SPEC-IDEN-002.
- DOM-OPS-002 §2.5 for non-identifying lifecycle outcomes.

The fixed-recipient, short-lived-code, aggregate-only-result protocol supersedes
nominated representatives and all-at-once code storage.

## V. Execution contract

Each code-entry command has one explicit class_id and requires the attempt access
nonce. Browser payloads carry only the public class reference, resolved to class_id
at ingress. Return an identical receipt for every submitted value, independently of
format, correctness, expiry or prior use. Record received_round separately from
private satisfied_round. Never return either recipient identity, generation time,
private validity, or which class failed.

Match only live current-round verifiers of the fixed recipients in that class.
Either recipient suffices. A match records class satisfied_at and satisfied_round,
then invalidates both outstanding codes in this same class transaction. A wrong
entry cannot erase an already accepted class proof or mutate another class.

The teacher submits the full set once collected. The User-owned coordinator checks only deposited
class results against the complete current ownership manifest. All classes satisfied in the current
round produces one setup nonce, with encrypted pending username/TOTP material. In that same local
transaction, apply DOM-IDEN-003 §VII.A supersession: advance credential generation, invalidate
existing sessions and outstanding authentication/routine-management grants, and record the
non-identifying audit event.

Bind setup to that generation. Repeating the same success cannot repeat invalidation or create a
second setup grant from the aggregate success itself. Recovery initiation alone has no such effect.
Otherwise increment submission_round and return a single generic failure. Previous-round codes and
proofs then become inert without a cross-class mutation sweep. Recipients remain frozen and all
classes require fresh codes. No progress endpoint exposes private satisfaction.

Resume PINs retain the attempt and confirmations without storing student codes.
A valid unambiguous PIN rotates the access nonce, invalidates old setup grants and, when the
attempt has already reached aggregate success, issues one replacement setup grant bound to the
current credential generation and the new nonce. That resume does not advance the generation
or repeat any invalidation.
This does not reset selections or silently renew the five-day deadline. Completion
is owned by FEAT-IDEN-106 and still checks the live nonce and complete proof set.

## VI. Mutation and verification

All changes occur in the owning FEAT transaction. Use server state and serialize
competing commands. Log no names, plaintext codes, nonce values or recipient list.
Tests must cover scope isolation, expiry, wrong input, replay, frozen selection,
concurrency and absence of per-code/per-class validity feedback.

**2026-11-23 amendment:** Applies the approved credential lifecycle contract, principal-scoped authority, generation supersession and provider/local completion distinction. No application implementation is asserted.

## VII. Amendment

Increment version/date, maintain the governing hierarchy, update SOP-DOC-001 and preserve
private class-confirmation behavior and the successful-aggregate supersession boundary.
