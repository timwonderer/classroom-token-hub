# FEAT-CLASS-011: Configuration Receipt Cleanup

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-CLASS-011 | 1.0 | 2026-10-25 | None | Normative |

## I. Purpose

Delete only expired temporary receipts in the explicitly authorized class, with logged count and reason. This command never decides token validity and never deletes audit history.

## II. Scope

One teacher Seat in one owned class; no apply-to-all or cross-class operation.

## III. Authority Level

Subordinate to INV-CORE, INV-ARC-006/007/014/019/021, DOM-CLASS-001 and DOM-POL-001.

## IV. Dependencies

- DOM-IDEN-003: export verification state
- DOM-CLASS-001: economics, enablement, temporary receipts
- DOM-POL-001: definitions
- DOM-OPS-002: transactional audit lineage
- FEAT-CORE-000: atomic execution and retry
- SPEC-CLASS-001: incorporated in full

## V. Contract

Delete only expired temporary receipts in the explicitly authorized class, with logged count and reason. This command never decides token validity and never deletes audit history.

All authorization uses fresh canonical class/seat authority. No source identifiers
or principal references enter destination definitions. Receipt lookup never bypasses
revocation or expiry. Exceptions and unsuccessful domain outcomes roll back the action.

## VI. Amendment

Increment version and effective date; preserve the frozen owner contract of 2026-10-25.
