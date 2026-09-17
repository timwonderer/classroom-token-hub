# FEAT-IDEN-103: Teacher Recovery Proof and Random Recipient Selection

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-IDEN-103 | 1.4 | 2026-09-17 | 1.3 | Normative |

## Governing authority

DOM-IDEN-003 §IX, INV-ARC-001/002/019 and incorporated SPEC-SEC-001.
The fixed-recipient, short-lived-code, aggregate-only-result protocol
supersedes nominated representatives and all-at-once code storage.

## Execution contract

One precheck command receives every join-code/username pair. Group pairs by join
code; every join code must resolve to a class owned by the same teacher User, and
the submitted classes must equal that User's owned class set. Evaluate each class's
usernames against that class's claimed student Seats. A class proof holds when the
distinct resolved students reach min(DOM-IDEN-003 §IX per-class requirement,
claimed count); fewer than three claimed students fails closed (DOM-IDEN-003 §IX
security posture). Track resolved user_ids in
memory for the command and fail when one student backs more than one pair. On any
failure create nothing and do not expose which pair failed.

On success, create the User-owned attempt with a five-day deadline, required class-ID
manifest, a random access nonce stored only as a verifier, and one proof result per
class. Never persist, log or return submitted usernames or resolved students. Require the exact full
class set before selecting anyone.

Within a separate class-scoped command, sample exactly two distinct claimed student
seat IDs using cryptographic randomness. Fewer than three eligible students fails
closed. Supplied usernames do not influence the sample. Sample each class
independently: never exclude, prefer or reweight a Seat because a Seat of the same
users.id exists or was selected in another class. Record selected_at
and selected_count once; repeated calls return without sampling again. Notify both
recipients and hide their identities. Serialize selection through teacher/attempt
locks so a second staged request cannot start another selected ceremony. Existing
selected attempts require their access nonce or resume PIN, never roster knowledge
alone. Pure account-level coordination combines ownership IDs and deposited proofs,
not cross-class roster reads.

## Mutation and verification

All changes occur in the owning FEAT transaction. Use server state and serialize
competing commands. Log no names, plaintext codes, nonce values or recipient list.
Tests must cover scope isolation, expiry, wrong input, replay, frozen selection,
concurrency and absence of per-code/per-class validity feedback.
