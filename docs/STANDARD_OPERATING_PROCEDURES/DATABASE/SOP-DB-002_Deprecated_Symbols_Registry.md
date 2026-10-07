# SOP-DB-002: Deprecated Symbols Registry

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DB-002 | 2.3 | 2026-10-07 | 2.2 | Normative |

## I. Purpose

Deprecated symbols are schema or model elements that have completed the **Contract phase** of the
Expand / Contract lifecycle (SOP-DB-001 §VIII, *Schema Contraction Policy*). Their table or column
no longer exists.

A deprecated symbol appearing again in application code signals:
- a reintroduced dependency on a structure that no longer exists;
- incomplete schema contraction;
- a high risk of production regression. Code that imports a removed model fails at import or at
  first use.

This registry turns past contractions into permanent guardrails.

## II. Scope

Symbols that are prohibited from appearing in first-party application code:

- `*.py`, `*.html`, `*.sh` and `*.js` under `app/`, `templates/` and `scripts/`;
- `*.js` under `static/`, except `static/vendor/`, which holds third-party code.

Tests, migrations and documentation are outside the scope. They name retired symbols lawfully, to
test their absence, to drop their tables, or to record their history.

## III. Authority Level

Normative (SOP Tier). Subordinate to INV-CORE-000, INV-ARC-019 and DOM-CORE-002.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`: the v2 identity model that replaced the v1 identity layer
- `docs/DOMAIN/DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`: the only valid set of runtime tables
- `docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-001_Migration_Specifications.md`: §VIII, *Schema Contraction Policy*
- `docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-003_Schema_Change_Proposals.md`: the Schema Change Gate, which enforces this registry
- `docs/STANDARD_OPERATING_PROCEDURES/DATABASE/DEPRECATED_SYMBOLS.txt`: the machine-readable list
- `tests/guards/deprecated_symbols.py`: the scanner, a pure function over file text (SOP-TEST-003 §IX.A)
- `tests/test_deprecated_symbols_guard.py`: the guard, with its mutation proofs
- `.github/workflows/policy-guardrails.yml`: runs the guard on every pull request and every push to `main`
- `.github/workflows/schema-gate.yml`: the *Audit Deprecated Symbols* step, which runs the same guard

## V. Rules

- The enforced list is `DEPRECATED_SYMBOLS.txt`, next to this document. This document and that file
  MUST list the same enforced symbols (§VI). A symbol listed here but absent from the file is not
  enforced.
- Symbols are **literal strings**, exactly as they would appear in code, one per line. Lines
  beginning with `#` are comments.
- No regex, wildcards or glob patterns. The scan is a case-sensitive substring match on each line,
  as `grep` is. A symbol inside a longer identifier, a string literal or a comment is reported.
- A symbol may be enforced only if a scan of the §II scope finds **no** occurrence of it. Clear every
  hit first, or the guard fails every pull request.
- The file MUST list at least one symbol. The guard fails on an empty file, which would enforce
  nothing while passing.
- A symbol whose literal also appears lawfully in code cannot be enforced this way. This covers a guard
  that must name it in order to forbid it, and a substring of a legitimate identifier. Record such a
  symbol in §VII, not in the file.
- Symbols may be removed from the registry only if the retired structure is being lawfully
  reintroduced through the Schema Change Gate.

## VI. Enforced Deprecated Symbols

The v1 identity layer and the v1 balance cache were contracted during the v1→v2 migration. None of
these exists as a model or a table (INV-ARC-019; DOM-CORE-002). Store bundles were contracted on
2026-10-03 (SPEC-STORE-001): their model attributes are gone, and their two `store_products` columns
remain only until the CONTRACT (DATABASE) migration drops them. The built-in hall-pass destination
preset was removed on 2026-10-07 by owner ruling (#1522). It was model behavior, not a column. It is
registered because a class without saved hall-pass settings must offer no destinations, so any
reintroduced preset is a defect (FEAT-PROD-002 §III; DOM-POL-001 §VII).

| Symbol | Replaced by | Status |
|--------|-------------|--------|
| `ClassMembership` | Membership by existence: a bound `Seat` (DOM-IDEN-005 §V, INV-ARC-013) | Enforced |
| `StudentTeacher` | `ClassEconomy.teacher_user_id` (class ownership) plus class-scoped `Seat` (INV-ARC-019) | Enforced |
| `TeacherBlock` | `ClassEconomy` (`classes`); `section` is display metadata only (INV-ARC-014) | Enforced |
| `StudentBlock` | `Seat`, scoped by `class_id` | Enforced |
| `BalanceCache` | `LedgerBalanceSnapshot` via `ledger_balance_query_service` (DOM-LED-001) | Enforced |
| `is_bundle` | A quantity bought at a bulk price (`bulk_discount_*`, SPEC-STORE-001) | Enforced |
| `bundle_quantity` | The purchase `quantity` (SPEC-STORE-001) | Enforced |
| `get_default_pass_types` | None. Destinations are only the ones the teacher saved (`HallPassSettings.get_pass_types()`); without settings, hall passes are unavailable | Enforced |

## VII. Retired Symbols Not Enforceable by Literal Scan

These are retired, and new code MUST NOT use them as scoping keys or model references. They stay out
of `DEPRECATED_SYMBOLS.txt` because their literal appears lawfully in code. Review catches them
instead, along with the multi-tenancy rules and the `CanonicalContext` guard, which raises on access.

| Symbol | Replaced by | Why not enforced |
|--------|-------------|------------------|
| `teacher_id` | `ClassEconomy.teacher_user_id` for ownership; `class_id` for scope | `CanonicalContext` names it in order to forbid it (`app/services/context_resolver.py`). It is also a substring of legitimate identifiers such as `teacher_ids` |
| `student_id` | `seat_id` (activity) and `users.id` (principal) | Named by the same `CanonicalContext` guard |
| `Student`, `Admin` | `User` plus `Seat` (INV-ARC-019) | Substrings of ordinary words and identifiers |
| `balance_cache`, `teacher_blocks`, `student_blocks` (table names) | As in §VI | `balance_cache` is a substring of the live helper `_get_balance_cache` (`ledger_balance_query_service.py`), which reads `LedgerBalanceSnapshot`, and it appears in the adversarial scripts. `teacher_blocks` and `student_blocks` appear in historical migration filenames listed by `scripts/validate-migrations.py` and in comments that record the contraction |

## VIII. Relationship to Schema Policy

This registry derives its authority from:

- SOP-DB-001 §VIII, *Schema Contraction Policy* ("Expand and Contract")
- SOP-DB-003, the Schema Change Gate (PR-blocking checklist)

The registry is enforced on **every** pull request. `policy-guardrails.yml` runs
`tests/test_deprecated_symbols_guard.py` on each pull request, whatever paths it touches, and again on
each push to `main`. The guard scans the whole §II scope, not only the changed lines, and needs no
database. A violation fails the pull request.

The Schema Change Gate runs the same guard in its *Audit Deprecated Symbols* step, so a model-changing
pull request reports the violation there too. That step runs whatever the classification, including
`NON-MODEL CHANGE`. There is one scanner; the two workflows only invoke it.

The guard also fails when this document's §VI table and `DEPRECATED_SYMBOLS.txt` list different
enforced symbols (§V).

Review remains the backstop only for the §VII symbols, which a literal scan cannot enforce.

## IX. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Keep `DEPRECATED_SYMBOLS.txt` in step with §VI in the same change.
4. Maintain consistency with `INV-CORE-000`, `INV-ARC-019` and `DOM-CORE-002`.

## X. Change Notes

**Version 2.3 (2026-10-07):**
- Enforced the registry on every pull request. Until 2.2 the scan ran only in the Schema Change Gate,
  which triggers on pull requests touching the model or migration paths and skipped the scan for
  `NON-MODEL CHANGE`. A pull request that brought back a deprecated symbol in a route, template or
  script without touching a model file was never scanned. The scan is now a pytest guard
  (`tests/test_deprecated_symbols_guard.py`) with mutation proofs (SOP-TEST-003 §IX.A). It runs from
  `policy-guardrails.yml` on every pull request and push to `main`, and it replaces the gate's inline
  `grep`.
- Widened §II to first-party JavaScript: `*.js` under `app/`, `templates/`, `scripts/` and `static/`,
  excluding `static/vendor/` (owner decision, 2026-10-07). A scan of that scope on 2026-10-07 found
  none of the §VI symbols.
- §V: the file must list at least one symbol, and the guard checks it against §VI. Version 2.0
  recorded the earlier failure, where an empty file enforced nothing.
- No symbol was added or removed.

**Version 2.2 (2026-10-07):**
- Registered `get_default_pass_types` in §VI and `DEPRECATED_SYMBOLS.txt`. The built-in hall-pass
  destination preset was removed by owner ruling (#1522). A scan of `app/`, `templates/` and `scripts/`
  on 2026-10-07 found no occurrence. As §VIII states, the audit runs only on pull requests that touch
  the model or migration paths, and it does not scan `static/`.

**Version 2.0 (2026-09-28):**
- Brought the registry to the v2 model. Version 1.2 listed `teacher_id` as "replaced by StudentTeacher
  association". `StudentTeacher` is itself a contracted v1 model, and `teacher_id` is replaced by
  `ClassEconomy.teacher_user_id` plus `class_id` scope.
- Reconciled the document with the enforced file. `DEPRECATED_SYMBOLS.txt` was empty ("Currently no
  symbols are deprecated"), so the registry enforced nothing. It now lists the five v1 model classes
  in §VI. A scan of `app/`, `templates/` and `scripts/` on 2026-09-28 found none of them.
- Moved `teacher_id` to §VII. Its literal must appear in the `CanonicalContext` guard, so a literal scan
  cannot enforce it.
- Named the real file (`DEPRECATED_SYMBOLS.txt`, not `deprecated_symbols.txt`), the scanned
  paths, and the governing documents by number. Added INV-ARC-019, DOM-CORE-002, SOP-DB-001, SOP-DB-003
  and the workflow as dependencies.
