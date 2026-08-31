# DOM-OPS-003: Bug Hunter Badge System

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-OPS-003      | 1.0     | 2026-08-30     | N/A        | Normative       |

## I. Purpose

Define the Operations domain's authority over the non-monetary Bug Hunter Badge System.
Badges recognize validated issue discoveries and cumulative breadth of discovery. They
do not represent money, ledger balance, entitlement, privilege, or access authority.
The concrete badge catalog and unlock rules are defined by `SPEC-OPS-001`.

## II. Authority and Dependencies

This document is subordinate to `INV-CORE-000`, `INV-CORE-001`, and the applicable
`INV-ARC` specifications. It is governed by:

- `DOM-OPS-001_OPERATIONS_DOMAIN.md`
- `INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`
- `FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`

## III. Ownership and Scope

The Operations domain owns badge-award records and the derived badge collection
projection. An award is attributed to one class-scoped operational actor (`seat_id`)
and one validated discovery. Internal `class_id` and `seat_id` must not be exposed on
student, teacher, sysadmin, or public-facing surfaces; external actor references use
`seats.public_id`.

Badges grant no capability and cannot be used as an authorization condition.

## IV. Badge-System Boundary

The Operations domain owns the badge-system state, award lineage, and presentation
authority described in `SPEC-OPS-001`. Badge recognition is triggered only by
validated issue-resolution evidence and the resulting distinct-badge collection.
The badge system is always enabled at the system level; teachers cannot grant, revoke,
disable, hide, or otherwise configure it.

Operations also owns detached certificate verification artifacts. These artifacts are
not class-scoped identity records and must not retain internal identity anchors.

## V. Monetary Separation

Bug Hunter badges replace monetary bug rewards. Issue resolution must not create a
ledger transaction, checking-account credit, bug-reward income, or monetary amount for
badge recognition.

## VI. Award Integrity

- Badge awards are idempotent per actor, badge identifier, and validated discovery.
- A single validated discovery must not produce duplicate awards.
- Badge awards and derived engineering unlocks must be auditable and correlated to the
  authorized issue-resolution FEAT.
- Badge state must be immutable after award unless a later authoritative correction
  workflow is defined.
- Failed or unvalidated issues must not contribute to any badge collection.

## VII. Presentation Boundary

Student views must display their own earned badge names, icons, award state, and
collection progress. Teacher views may display earned badge names, icons, award state,
and collection progress for students in the current class. Operations/sysadmin views
may display public actor references and operational badge records. No teacher or
sysadmin control may hide or disable the feature. No presentation surface may expose
`class_id`, `seat_id`, `user_id`, or other internal identity anchors.

## VIII. Specification Boundary

`SPEC-OPS-001` defines the concrete badge catalog, 2/4/6 unlock progression, award
event schema, issue-resolution FEAT contract, correction/revocation behavior, and read
projection. `SPEC-OPS-002` defines the user-facing presentation and accessibility
contract before implementation begins.

## IX. Amendment

Revisions must increment the version number, update the effective date, preserve the
non-monetary separation, and remain consistent with `SPEC-OPS-001` and `SPEC-OPS-002`.
