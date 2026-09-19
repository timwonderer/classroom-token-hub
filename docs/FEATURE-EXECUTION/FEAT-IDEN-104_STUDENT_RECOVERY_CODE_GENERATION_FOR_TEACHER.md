# FEAT-IDEN-104: Student Recovery Code Issuance

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-IDEN-104 | 1.3 | 2026-09-15 | 1.2 | Normative |

## Governing authority

DOM-IDEN-003 §IX, INV-ARC-001/002/019 and incorporated SPEC-SEC-001.
The fixed-recipient, short-lived-code, aggregate-only-result protocol
supersedes nominated representatives and all-at-once code storage.

## Execution contract

Require explicit class_id, selected code/Seat IDs, and authenticated principal.
Recheck the attempt's original expiry, selected class challenge, live Seat binding,
and passphrase inside the FEAT transaction. Issue a random six-digit ASCII code and
replace only this recipient's verifier. Set issued_round to the current attempt
round and expiry to min(now + 30 minutes, attempt expiry). Regeneration uses the
same Seat; it never samples replacement recipients.

Either selected student can request fresh codes through their prompt. Both are
notified immediately. Display the plaintext only in the issuance response, with
an instruction to hand it to the teacher in person only while the teacher is with
this class. Use the request/class-bound HMAC contract in SPEC-SEC-001. If this class
already has a private confirmation in this round, issue no more codes.

Unclaim/deletion revokes only the affected recipient row. Never reroll; another
selected recipient may still confirm. An accepted class proof survives recipient
removal while the class and attempt exist.

## Mutation and verification

All changes occur in the owning FEAT transaction. Use server state and serialize
competing commands. Log no names, plaintext codes, nonce values or recipient list.
Tests must cover scope isolation, expiry, wrong input, replay, frozen selection,
concurrency and absence of per-code/per-class validity feedback.
