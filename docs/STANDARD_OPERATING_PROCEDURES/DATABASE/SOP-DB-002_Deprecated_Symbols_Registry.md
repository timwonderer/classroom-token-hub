# SOP-DB-002: Deprecated Symbols Registry

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DB-002 | 2.0 | 2026-09-28 | 1.2 | Normative |

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

Symbols that are prohibited from appearing in application code: `app/`, `templates/` and
`scripts/` (`*.py`, `*.html`, `*.sh`).

## III. Authority Level

Normative (SOP Tier). Subordinate to INV-CORE-000, INV-ARC-019 and DOM-CORE-002.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`: the v2 identity model that replaced the v1 identity layer
- `docs/DOMAIN/DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`: the only valid set of runtime tables
- `docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-001_Migration_Specifications.md`: §VIII, *Schema Contraction Policy*
- `docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-003_Schema_Change_Proposals.md`: the Schema Change Gate, which enforces this registry
- `docs/STANDARD_OPERATING_PROCEDURES/DATABASE/DEPRECATED_SYMBOLS.txt`: the machine-readable list
- `.github/workflows/schema-gate.yml`: the *Audit Deprecated Symbols* step

## V. Rules

- The enforced list is `DEPRECATED_SYMBOLS.txt`, next to this document. This document and that file
  MUST list the same enforced symbols (§VI). A symbol listed here but absent from the file is not
  enforced.
- Symbols are **literal strings**, exactly as they would appear in code, one per line. Lines
  beginning with `#` are comments.
- No regex, wildcards or glob patterns. The gate runs `grep -r <symbol>`, which is a substring match.
- A symbol may be enforced only if a scan of `app/`, `templates/` and `scripts/` finds **no**
  occurrence of it. Clear every hit first, or the gate fails every model-changing pull request.
- A symbol whose literal also appears lawfully in code cannot be enforced this way. This covers a guard
  that must name it in order to forbid it, and a substring of a legitimate identifier. Record such a
  symbol in §VII, not in the file.
- Symbols may be removed from the registry only if the retired structure is being lawfully
  reintroduced through the Schema Change Gate.

## VI. Enforced Deprecated Symbols

The v1 identity layer and the v1 balance cache were contracted during the v1→v2 migration. None of
these exists as a model or a table (INV-ARC-019; DOM-CORE-002).

| Symbol | Replaced by | Status |
|--------|-------------|--------|
| `ClassMembership` | Membership by existence: a bound `Seat` (DOM-IDEN-005 §V, INV-ARC-013) | Enforced |
| `StudentTeacher` | `ClassEconomy.teacher_user_id` (class ownership) plus class-scoped `Seat` (INV-ARC-019) | Enforced |
| `TeacherBlock` | `ClassEconomy` (`classes`); `section` is display metadata only (INV-ARC-014) | Enforced |
| `StudentBlock` | `Seat`, scoped by `class_id` | Enforced |
| `BalanceCache` | `LedgerBalanceSnapshot` via `ledger_balance_query_service` (DOM-LED-001) | Enforced |

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

A violation of this registry is a Schema Change Gate failure. The gate runs only on pull requests that
touch `migrations/versions/**`, `app/models.py` or `app/models/**`. On those, it runs the deprecated-symbol
audit unless the pull request is classified `NON-MODEL CHANGE`. That classification is allowed only when
no migration file changed and the model files show no structural AST change once comments and docstrings
are removed; otherwise the classification check fails the gate. A pull request that changes only
`app/`, `templates/` or `scripts/` outside those paths does not trigger the audit, so review remains the
backstop there.

## IX. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Keep `DEPRECATED_SYMBOLS.txt` in step with §VI in the same change.
4. Maintain consistency with `INV-CORE-000`, `INV-ARC-019` and `DOM-CORE-002`.

## X. Change Notes

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
