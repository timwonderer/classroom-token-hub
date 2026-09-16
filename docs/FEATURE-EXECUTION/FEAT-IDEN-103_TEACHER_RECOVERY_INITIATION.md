# FEAT-IDEN-103: Teacher Recovery Proof and Random Recipient Selection

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-IDEN-103 | 1.3 | 2026-09-15 | 1.2 | Normative |

## Governing authority

DOM-IDEN-003 §IX, INV-ARC-001/002/019 and incorporated SPEC-SEC-001.
The fixed-recipient, short-lived-code, aggregate-only-result protocol
supersedes nominated representatives and all-at-once code storage.

## Execution contract

Create a User-owned staged attempt with a five-day deadline, required class-ID
manifest, and a random access nonce stored only as a verifier. Each submitted
join-code/username pair is evaluated in a separate explicit class scope. Deposit
only its proof result; do not expose which pair succeeded. Require the exact full
class set before selecting anyone.

Within a separate class-scoped command, sample min(2, eligible count) distinct
claimed student seat IDs using cryptographic randomness. Zero eligible students
fails closed. Supplied usernames do not influence the sample. Record selected_at
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
