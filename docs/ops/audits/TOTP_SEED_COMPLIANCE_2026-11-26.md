# TOTP seed compliance count, 2026-11-26

Record for `SOP-DEP-002` §VII.C stage 4: the aggregate, per-role count of stored TOTP seeds below the
`SPEC-SEC-001` §V.1 item 7 minimum. It names no principal, seed or seed material.

## 1. Method

An aggregate-only, per-role count of the decoded bit length of every stored TOTP seed
(`users.totp_secret_encrypted`), run in a `flask shell` on the production host at 2026-11-26 21:46 UTC.
Bit length is five bits per base32 character of the decrypted seed. The shell printed counts only. No
seed, decrypted value, username or identifier was printed, logged or retained.

The floor is 112 bits (`SPEC-SEC-001` §V.1 item 7). `pyotp` 2.12 and later raises `ValueError` when a
`TOTP` is constructed from a seed below it.

## 2. Result

| Role | Seed length (bits) | Principals |
|---|---|---|
| teacher | 160 | 8 |
| sysadmin | 160 | 1 |
| teacher | below 112 | 0 |
| sysadmin | below 112 | 0 |
| any other role | below 112 | 0 |

## 3. Conclusion

No stored seed is below the floor, for any role. The §VII.C stage 4 condition is satisfied, so the
`pyotp` pin may be raised (stage 5, `pyotp==2.12.1`).

## 4. Why the stage 3 window was not needed

CTH's seed generator has produced 160-bit seeds (32 base32 characters, the `pyotp.random_base32()` default
since `pyotp` 2.4.0) since CTH first pinned `pyotp` 2.9.0 in 2025-06. Every seed CTH minted was therefore
already at or above the floor, and the count above was already zero when measured. The stage 3 window, in
which principals replace noncompliant seeds through the credential compliance gate, had nothing to
replace. Stages 1 and 2 (lifecycle contracts, the single 160-bit generator and the compliance check)
remain in force as the guard against a future noncompliant seed.
