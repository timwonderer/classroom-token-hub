# SOP-CORE-000: Standard Operating Procedures Foundation

| Reference Number | Version | Effective Date | Supersedes | Authority Level  |
|------------------|---------|----------------|------------|------------------|
| SOP-CORE-000 | 1.2 | 2026-09-17 | 1.1 | Constitutional |

---

## I. Purpose

This document defines the scope, structure, subdivisions, and authoring rules for the `STANDARD_OPERATING_PROCEDURES` namespace in the Classroom Token Hub documentation.

## II. Scope

The `STANDARD_OPERATING_PROCEDURES` (SOP) namespace governs **human procedures** and governance outside of application runtime behavior. It dictates how developers, administrators, and contributors interact with the repository, deployments, and databases.

SOP documents are binding rules for humans, not for application code.

## III. Authority Level

Constitutional (Tier 1) within the context of human procedure, but explicitly subordinate to `INV-CORE-000` and `ARC/DOM` structures. SOP documents cannot dictate architectural behavior.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`

## V. Subdivisions

The `STANDARD_OPERATING_PROCEDURES` namespace is organized into the following subdivisions:

- `DATABASE/` (SOP-DB-*): Migrations, backfills, schema-change gating, and state management.
- `DEPLOYMENT/` (SOP-DEP-*): Live-test and production-transition procedures for releasing code.
- `DEVOPS/` (SOP-DEV-*): Refactor and domain-reconstruction procedures.
- `OPERATIONS/` (SOP-OPS-*): Operating the systems that carry out the Operations domain's purpose, including status publication and incident communication.
- `SECURITY/` (SOP-SEC-*): Credential, key-custody, and identity-lookup operations.
- `TESTING/` (SOP-TEST-*): Validation execution, test creation, and PR gates.

`SOP-CORE-000`, `SOP-DOC-000` and `SOP-DOC-001` sit at the namespace root rather
than in a subdivision: they govern the namespace itself. There is no
`DOCUMENTATION/` or `WORKFLOW/` subdivision — earlier revisions of this section
listed both, and neither has ever existed in the v2 tree.

### Numbering

Each subdivision numbers from `001` upward with no gaps, in the order documents
were issued. A retired document's number is not reissued within the same
subdivision. Numbers used by archived v1 documents under `docs/archive/` are
available for reuse: those identifiers are retired with the v1 line and carry
no authority, so a bare v1 identifier must be read with its archive path.

On 2026-09-17 the surviving namespace was renumbered to close the gaps left by
quarantining superseded documents. The mapping, for resolving older citations:

| Former | Current |
|--------|---------|
| SOP-DB-011 | SOP-DB-001 |
| SOP-DB-014 | SOP-DB-002 |
| SOP-DB-015 | SOP-DB-003 |
| SOP-DEP-022 | SOP-DEP-001 |
| SOP-DEP-023 | SOP-DEP-002 |
| SOP-DOC-002 | SOP-DOC-001 |

Citations in merged migration files and in `CHANGELOG.md` are left at their
former identifiers: both are historical records of what was cited when the
entry was written, and this table resolves them.

## VI. Standard Document Template

All documents within the `STANDARD_OPERATING_PROCEDURES` namespace must follow the standard normative template defined in `SOP-DOC-000`:

1. **I. Purpose**
2. **II. Scope**
3. **III. Authority Level**
4. **IV. Dependencies**
5. **[V+] Content Sections**
6. **[Last] Amendment** (Must specify procedure for altering the SOP)

## VII. Amendment

Revisions to this document require a version increment, an update to the Effective Date, and must maintain consistency with `INV-CORE-000`.
