# FEAT-IDEN-105: Private Class Confirmation and Aggregate Validation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-IDEN-105 | 1.3 | 2026-09-15 | 1.2 | Normative |

## Governing authority

DOM-IDEN-003 §IX, INV-ARC-001/002/019 and incorporated SPEC-SEC-001.
The fixed-recipient, short-lived-code, aggregate-only-result protocol
supersedes nominated representatives and all-at-once code storage.

## Execution contract

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

The teacher submits the full set once collected. The User-owned coordinator checks
only deposited class results against the complete current ownership manifest.
All classes satisfied in the current round produces one setup nonce, with encrypted
pending username/TOTP material. Otherwise increment submission_round and return a
single generic failure. Previous-round codes and proofs then become inert without
a cross-class mutation sweep. Recipients remain frozen and all classes require
fresh codes. No progress endpoint exposes private satisfaction.

Resume PINs retain the attempt and confirmations without storing student codes.
A valid unambiguous PIN rotates the access nonce and invalidates old setup grants.
This does not reset selections or silently renew the five-day deadline. Completion
is owned by FEAT-IDEN-106 and still checks the live nonce and complete proof set.

## Mutation and verification

All changes occur in the owning FEAT transaction. Use server state and serialize
competing commands. Log no names, plaintext codes, nonce values or recipient list.
Tests must cover scope isolation, expiry, wrong input, replay, frozen selection,
concurrency and absence of per-code/per-class validity feedback.
