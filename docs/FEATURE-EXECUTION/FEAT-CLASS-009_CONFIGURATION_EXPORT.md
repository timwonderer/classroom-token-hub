# FEAT-CLASS-009: Configuration Export

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-CLASS-009 | 1.0 | 2026-10-25 | None | Normative |

## I. Purpose

Issue a signed current-only file for one class. Validate selections and size before rotating the Identity reference. GET selection is pure; issuance is a CSRF-protected POST. Return bytes after commit.

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

Issue a signed current-only file for one class. Validate selections and size before rotating the Identity reference. GET selection is pure; issuance is a CSRF-protected POST. Return bytes after commit.

All authorization uses fresh canonical class/seat authority. No source identifiers
or principal references enter destination definitions. Receipt lookup never bypasses
revocation or expiry. Exceptions and unsuccessful domain outcomes roll back the action.

## VI. Amendment

Increment version and effective date; preserve the frozen owner contract of 2026-10-25.
