# Roster deduplication and claim — manual test rosters

Demo names for exercising system-assigned claim codes (FEAT-IDEN-006, additive
roster import) and the student claim flow (FEAT-IDEN-001).

`tests/dom/identity/test_roster_dedupe_artifacts.py` imports both files through the
upload route and claims through FEAT-IDEN-001, asserting each row's
`Expect Claim Code` value. Edit a row and its expectation together, or the test fails.

The Add Students grid takes pasted spreadsheet rows, not CSV uploads. Open a file
in a spreadsheet, copy the rows **below the header**, and paste into the grid. The
grid reads only the first three columns, so `Expect Claim Code` is ignored.

## Batch 1 — first import

| Case | Rows | Expected |
|---|---|---|
| Unique | Ava Martinez, Liam Chen, Noah Patel | No code; claim by name alone |
| Duplicate pair | Sofia Nguyen ×2 | Two distinct codes; name alone is ambiguous |
| Triple | Ethan Brooks ×3 | Three distinct codes |
| Case variant | Maya Okafor / MAYA okafor | One name group (NFKC + lowercase); both get codes |
| Accent differs | Zoë Kim / Zoe Kim | Distinct names; no codes |

## Batch 2 — import after batch 1

1. **Liam Chen** — the existing unclaimed Liam receives a code; the new seat gets a different one.
2. **Sofia Nguyen** — existing codes are kept; the third seat gets a new distinct code.
3. **Ava Martinez** — claim batch 1's Ava first. Claimed seats drop their claim
   material, so the new Ava needs no code.
4. **Riley Johnson** — unique; no code.

## Claim checks

- Codes appear in the Claim code column of Unclaimed Seats.
- A wrong code returns "Invalid deduplication code".
- Lowercase codes work (the claim form uppercases input).
- A claimed seat leaves the unclaimed list.
