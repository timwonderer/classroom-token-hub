# SOP-DOC-001: Documentation Index

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DOC-001      | 3.4     | 2026-09-19     | 3.3        | Normative |

---

## I. Purpose

This document is the canonical master index of all formal documentation within the Classroom Token Hub (CTH) repository. It lists every numbered constitutional, normative, and informative document, and records where superseded v1 material is archived (§VI). Completeness is the point: a partial index reads exactly like a complete one.

---

## II. Scope

This index tracks all formally registered, numbered documents. The following folders/files are intentionally out of scope:
- `docs/user-guides/` (User-facing help/tutorials)
- `docs/README.md` (General repository navigation)

---

## III. Authority Level

Normative (Tier 2). Subordinate to Core and Constitutional Invariants (`INV-CORE-000`, `INV-CORE-001`).

---

## IV. Dependencies

- `docs/STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md`
- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`

---

## V. Registered Documents

Every numbered document in the repository, by namespace, ordered by reference number.
Archived material is deliberately absent; see §VI.

### Invariants — Core (INV-CORE)
- [INV-CORE-000 — Core Invariants](../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md)
- [INV-CORE-001 — Capability Based Architecture and Authority Model](../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md)

### Invariants — Architecture (INV-ARC)
- [INV-ARC-000 — Execution Model](../INVARIANT/ARCHITECTURE/INV-ARC-000_EXECUTION_MODEL.md)
- [INV-ARC-001 — Scoped Request Context](../INVARIANT/ARCHITECTURE/INV-ARC-001_SCOPED_REQUEST_CONTEXT.md)
- [INV-ARC-002 — No Implicit Global Access](../INVARIANT/ARCHITECTURE/INV-ARC-002_NO_IMPLICIT_GLOBAL_ACCESS.md)
- [INV-ARC-003 — Scoped Capability Evaluation](../INVARIANT/ARCHITECTURE/INV-ARC-003_SCOPED_CAPABILITY_EVALUATION.md)
- [INV-ARC-004 — Cross Tenant Isolation](../INVARIANT/ARCHITECTURE/INV-ARC-004_CROSS_TENANT_ISOLATION.md)
- [INV-ARC-005 — No PII Leakage in Execution Layer](../INVARIANT/ARCHITECTURE/INV-ARC-005_NO_PII_LEAKAGE_IN_EXECUTION_LAYER.md)
- [INV-ARC-006 — Command Boundary for Mutation](../INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md)
- [INV-ARC-007 — GET Must Be Pure](../INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md)
- [INV-ARC-008 — Identity Resolution and Seat Scope](../INVARIANT/ARCHITECTURE/INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md)
- [INV-ARC-009 — Domain Authority for State](../INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md)
- [INV-ARC-010 — Explicit Context Switching](../INVARIANT/ARCHITECTURE/INV-ARC-010_EXPLICIT_CONTEXT_SWITCHING.md)
- [INV-ARC-011 — No Phantom Scope Access](../INVARIANT/ARCHITECTURE/INV-ARC-011_NO_PHANTOM_SCOPE_ACCESS.md)
- [INV-ARC-012 — Hard Deletion Enforcement](../INVARIANT/ARCHITECTURE/INV-ARC-012_HARD_DELETION_ENFORCEMENT.md)
- [INV-ARC-013 — Membership by Existence](../INVARIANT/ARCHITECTURE/INV-ARC-013_MEMBERSHIP_BY_EXISTENCE.md)
- [INV-ARC-014 — No Label Based Logic](../INVARIANT/ARCHITECTURE/INV-ARC-014_NO_LABEL_BASED_LOGIC.md)
- [INV-ARC-015 — Temporal Model and Boundary Enforcement](../INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md)
- [INV-ARC-016 — Lawful Existence and Audit Lineage](../INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md)
- [INV-ARC-017 — General Testing Invariants](../INVARIANT/ARCHITECTURE/INV-ARC-017_GENERAL_TESTING_INVARIANTS.md)
- [INV-ARC-018 — PII Storage and Retention Enforcement](../INVARIANT/ARCHITECTURE/INV-ARC-018_PII_STORAGE_AND_RETENTION_ENFORCEMENT.md)
- [INV-ARC-019 — Identity and Ownership Model](../INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md)
- [INV-ARC-020 — Accessibility Requirements and Template Contract](../INVARIANT/ARCHITECTURE/INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md)
- [INV-ARC-021 — Cross-Domain Reference and Coordination Semantics](../INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md)
- [INV-ARC-022 — Request Context and Page Rendering Pipeline](../INVARIANT/ARCHITECTURE/INV-ARC-022_REQUEST_CONTEXT_AND_PAGE_RENDERING.md)

### Domains (DOM)
- [DOM-CLASS-001 — Class Configuration Domain](../DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md)
- [DOM-CLASS-002 — Class Economy Governance](../DOMAIN/DOM-CLASS-002_CLASS_ECONOMY_GOVERNANCE.md)
- [DOM-CLASS-003 — Economic Policy](../DOMAIN/DOM-CLASS-003_ECONOMIC_POLICY.md)
- [DOM-CORE-000 — Domain Foundation](../DOMAIN/DOM-CORE-000_DOMAIN_FOUNDATION.md)
- [DOM-CORE-001 — Domain Authority Summary](../DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md)
- [DOM-CORE-002 — Canonical Schema Definition](../DOMAIN/DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md)
- [DOM-IDEN-001 — Canonical Identity Model](../DOMAIN/DOM-IDEN-001_CANONICAL_IDENTITY_MODEL.md)
- [DOM-IDEN-002 — Student Identity Architecture](../DOMAIN/DOM-IDEN-002_STUDENT_IDENTITY_ARCHITECTURE.md)
- [DOM-IDEN-003 — Teacher Identity Architecture](../DOMAIN/DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md)
- [DOM-IDEN-005 — Identity Binding and Lifecycle](../DOMAIN/DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md)
- [DOM-IDEN-006 — Canonical Context Resolution](../DOMAIN/DOM-IDEN-006_CANONICAL_CONTEXT_RESOLUTION.md)
- [DOM-IDEN-007 — Identity Models and References](../DOMAIN/DOM-IDEN-007_Identity_Models_and_References.md)
- [DOM-ITR-001 — Interpretation Domain](../DOMAIN/DOM-ITR-001_INTERPRETATION_DOMAIN.md)
- [DOM-LED-001 — Ledger Domain](../DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md)
- [DOM-OBL-001 — Obligations Domain](../DOMAIN/DOM-OBL-001_OBLIGATIONS_DOMAIN.md)
- [DOM-OPS-001 — Operations Domain](../DOMAIN/DOM-OPS-001_OPERATIONS_DOMAIN.md)
- [DOM-OPS-002 — Audit Lineage Integrity](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md)
- [DOM-POL-001 — Policies Domain](../DOMAIN/DOM-POL-001_POLICIES_DOMAIN.md)
- [DOM-POL-001A — Policies Schema Appendix](../DOMAIN/DOM-POL-001A_POLICY_SCHEMA_APPENDIX.md)
- [DOM-PROD-001 — Productivity and Payroll Domain](../DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md)
- [DOM-STORE-001 — Store and Entitlements Domain](../DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md)
- [DOM-SUP-001 — Support Domain](../DOMAIN/DOM-SUP-001_SUPPORT_DOMAIN.md)

### Feature Execution (FEAT)
- [FEAT-CLASS-001 — Creating New Class Boundary](../FEATURE-EXECUTION/FEAT-CLASS-001_CREATING_NEW_CLASS_BOUNDARY.md)
- [FEAT-CLASS-002 — Modifying Existing Class Boundary](../FEATURE-EXECUTION/FEAT-CLASS-002_MODIFYING_EXISTING_CLASS_BOUNDARY.md)
- [FEAT-CLASS-003 — Insurance Policy Management](../FEATURE-EXECUTION/FEAT-CLASS-003_INSURANCE_POLICY_MANAGEMENT.md)
- [FEAT-CLASS-004 — Feature Enablement](../FEATURE-EXECUTION/FEAT-CLASS-004_FEATURE_ENABLEMENT.md)
- [FEAT-CLASS-005 — Economic Engine Evolution](../FEATURE-EXECUTION/FEAT-CLASS-005_ECONOMIC_ENGINE_EVOLUTION.md)
- [FEAT-CLASS-006 — Destroying a Class Boundary](../FEATURE-EXECUTION/FEAT-CLASS-006_DESTROYING_CLASS_BOUNDARY.md)
- [FEAT-CORE-000 — Feature Execution Constitutional Directive](../FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md)
- [FEAT-ECON-001 — Economic Policy Transition Execution and Activation Orchestration](../FEATURE-EXECUTION/FEAT-ECON-001_ECONOMIC_POLICY_TRANSITION_EXECUTION_AND_ACTIVATION_ORCHESTRATION.md)
- [FEAT-IDEN-001 — Unauthenticated Student Seat Claim](../FEATURE-EXECUTION/FEAT-IDEN-001_UNAUTHENTICATED_STUDENT_SEAT_CLAIM_REMEDIATED.md)
- [FEAT-IDEN-002 — Student Credential Setup](../FEATURE-EXECUTION/FEAT-IDEN-002_STUDENT_CREDENTIAL_SETUP.md)
- [FEAT-IDEN-003 — Teacher-Initiated Reset Code Generation](../FEATURE-EXECUTION/FEAT-IDEN-003_TEACHER_RESET_CODE_GENERATION.md)
- [FEAT-IDEN-004 — Student Recovery Code Acceptance & Session Authorization](../FEATURE-EXECUTION/FEAT-IDEN-004_STUDENT_RECOVERY_CODE_VALIDATION.md)
- [FEAT-IDEN-006 — Provision Student Seat in Existing Class](../FEATURE-EXECUTION/FEAT-IDEN-006_PROVISION_STUDENT_SEAT.md)
- [FEAT-IDEN-007 — Teacher Account Destruction](../FEATURE-EXECUTION/FEAT-IDEN-007_TEACHER_ACCOUNT_DESTRUCTION.md)
- [FEAT-IDEN-101 — Teacher TOTP Setup](../FEATURE-EXECUTION/FEAT-IDEN-101_TEACHER_TOTP_SETUP.md)
- [FEAT-IDEN-102 — Teacher Passkey Enrollment](../FEATURE-EXECUTION/FEAT-IDEN-102_TEACHER_PASSKEY_ENROLLMENT.md)
- [FEAT-IDEN-103 — Teacher Recovery Proof and Random Recipient Selection](../FEATURE-EXECUTION/FEAT-IDEN-103_TEACHER_RECOVERY_INITIATION.md)
- [FEAT-IDEN-104 — Student Recovery Code Issuance](../FEATURE-EXECUTION/FEAT-IDEN-104_STUDENT_RECOVERY_CODE_GENERATION_FOR_TEACHER.md)
- [FEAT-IDEN-105 — Private Class Confirmation and Aggregate Validation](../FEATURE-EXECUTION/FEAT-IDEN-105_TEACHER_RECOVERY_CODE_VALIDATION.md)
- [FEAT-IDEN-106 — Teacher Update TOTP Secret](../FEATURE-EXECUTION/FEAT-IDEN-106_TEACHER_UPDATE_TOTP_SECRET.md)
- [FEAT-IDEN-107 — Teacher Revoke Passkey](../FEATURE-EXECUTION/FEAT-IDEN-107_TEACHER_REVOKE_PASSKEY.md)
- [FEAT-LED-000 — Canonical Monetary Resolution Workflow](../FEATURE-EXECUTION/FEAT-LED-000_CANONICAL_MONETARY_RESOLUTION_WORKFLOW.md)
- [FEAT-LED-001 — Post Ledger Transaction](../FEATURE-EXECUTION/FEAT-LED-001_POST_LEDGER_TRANSACTION.md)
- [FEAT-LED-002 — Reversal of Monetary Transaction](../FEATURE-EXECUTION/FEAT-LED-002_VOID_REVERSE_TRANSACTION.md)
- [FEAT-OBL-002 — Advance Bill Cycle](../FEATURE-EXECUTION/FEAT-OBL-002_ADVANCE_BILL_CYCLE.md)
- [FEAT-OBL-003 — Satisfy Obligation](../FEATURE-EXECUTION/FEAT-OBL-003_SATISFY_OBLIGATION.md)
- [FEAT-OBL-004 — Insurance Policy Purchase / Enrollment](../FEATURE-EXECUTION/FEAT-OBL-004_INSURANCE_POLICY_PURCHASE.md)
- [FEAT-OBLI-001 — Assess Obligation](../FEATURE-EXECUTION/FEAT-OBLI-001_ASSESS_OBLIGATION.md)
- [FEAT-OPS-001 — Audit Protected Emission](../FEATURE-EXECUTION/FEAT-OPS-001_AUDIT_PROTECTED_EMISSION.md)
- [FEAT-POL-001 — Policy Reference Management](../FEATURE-EXECUTION/FEAT-POL-001_POLICY_REFERENCE_MANAGEMENT.md)
- [FEAT-PROD-001 — Record Attendance Session](../FEATURE-EXECUTION/FEAT-PROD-001_RECORD_ATTENDANCE_SESSION.md)
- [FEAT-PROD-002 — Record Hall Pass Log](../FEATURE-EXECUTION/FEAT-PROD-002_RECORD_HALL_PASS_LOG.md)
- [FEAT-PROD-003 — Record Payroll Event](../FEATURE-EXECUTION/FEAT-PROD-003_RECORD_PAYROLL_EVENT.md)
- [FEAT-PROD-004 — Complete Payroll Cycle](../FEATURE-EXECUTION/FEAT-PROD-004_COMPLETE_PAYROLL_CYCLE.md)
- [FEAT-STOR-001 — Store Purchase and Entitlement Grant](../FEATURE-EXECUTION/FEAT-STOR-001_STORE_PURCHASE.md)
- [FEAT-STOR-002 — Entitlement Lifecycle Transition](../FEATURE-EXECUTION/FEAT-STOR-002_ENTITLEMENT_LIFECYCLE_TRANSITION.md)
- [FEAT-STOR-003 — Insurance Claim Lifecycle](../FEATURE-EXECUTION/FEAT-STOR-003_INSURANCE_CLAIM_LIFECYCLE.md)
- [FEAT-STOR-004 — Direct Entitlement Grant](../FEATURE-EXECUTION/FEAT-STOR-004_DIRECT_ENTITLEMENT_GRANT.md)
- [FEAT-SUP-001 — Issue Submission and Escalation](../FEATURE-EXECUTION/FEAT-SUP-001_ISSUE_SUBMISSION_AND_ESCALATION.md)
- [FEAT-SUP-002 — Class Announcement Management](../FEATURE-EXECUTION/FEAT-SUP-002_CLASS_ANNOUNCEMENT_MANAGEMENT.md)

### Specifications (SPEC)
- [SPEC-DES-001 — Design System and Visual Identity](../SPEC/SPEC-DES-001_DESIGN_SYSTEM_AND_VISUAL_IDENTITY.md)
- [SPEC-DISPLAY-001 — Display Metadata Resolver](../SPEC/SPEC-DISPLAY-001_DISPLAY_IDENTITY_METADATA_RESOLVER.md)
- [SPEC-ECON-001 — Savings Interest Accrual and Disbursement Specification](../SPEC/SPEC-ECON-001_SAVINGS_INTEREST_ACCRUAL_AND_DISBURSEMENT_SPECIFICATION.md)
- [SPEC-ECON-002 — Economic Policy Visibility and Disclosure](../SPEC/SPEC-ECON-002_ECONOMIC_POLICY_VISIBILITY_AND_DISCLOSURE.md)
- [SPEC-ECON-003 — Economic Engine Calculation and Reference Specification](../SPEC/SPEC-ECON-003_ECONOMIC_ENGINE_CALCULATION_AND_REFERENCE_SPECIFICATION.md)
- [SPEC-INV-001 — Invariant Enforcement via Continuous Integration](../SPEC/SPEC-INV-001_INVARIANT_ENFORCEMENT_VIA_CI.md)
- [SPEC-ITR-001 — Interpretation Observation Specification](../SPEC/SPEC-ITR-001_INTERPRETATION_OBSERVATION_SPECIFICATION.md)
- [SPEC-LED-001 — Ledger Verification Proof Surfaces](../SPEC/SPEC-LED-001_LEDGER_VERIFICATION_PROOF_SURFACES.md)
- [SPEC-LED-002 — Command Idempotency Reservation and Structural Enforcement](../SPEC/SPEC-LED-002_COMMAND_IDEMPOTENCY_RESERVATION_AND_ENFORCEMENT.md)
- [SPEC-OPS-001 — Reversal, Void, and Transaction Finality Specification](../SPEC/SPEC-OPS-001_REVERSAL_AND_VOID.md)
- [SPEC-OPS-002 — External Status Persistence Model](../SPEC/SPEC-OPS-002_EXTERNAL_STATUS_PERSISTENCE_MODEL.md)
- [SPEC-OPS-003 — Application Observability Contract](../SPEC/SPEC-OPS-003_APPLICATION_OBSERVABILITY_CONTRACT.md)
- [SPEC-OPS-004 — System Administration Console](../SPEC/SPEC-OPS-004_SYSTEM_ADMINISTRATION_CONSOLE.md)
- [SPEC-SEC-001 — Credentials and Identity Lookup Code Contract](../SPEC/SPEC-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_CODE_CONTRACT.md)
- [SPEC-STORE-001 — Store Product Policy Payload Schema](../SPEC/SPEC-STORE-001_PRODUCT_POLICY_PAYLOAD_SCHEMA.md)
- [SPEC-TEST-001 — Canonical Test Initializer](../SPEC/SPEC-TEST-001_CANONICAL_TEST_INITIALIZER.md)
- [SPEC-TEST-002 — Canonical Test Identities](../SPEC/SPEC-TEST-002_CANONICAL_TEST_IDENTITIES.md)
- [SPEC-TIME-001 — Canonical Temporal Resolver](../SPEC/SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md)
- [SPEC-UI-001 — Canonical Page Rendering Specification](../SPEC/SPEC-UI-001_PAGE_RENDERING_SPECIFICATION.md)

### Standards & Procedures (SOP)
- [SOP-CORE-000 — Standard Operating Procedures Foundation](SOP-CORE-000_Sop_Foundation.md)
- [SOP-DOC-000 — Documentation Standard](SOP-DOC-000_DOCUMENTATION_STANDARD.md)
- [SOP-DOC-001 — Documentation Index](SOP-DOC-001_DOCUMENTATION_INDEX.md)

### Procedures — Database (SOP-DB)
- [SOP-DB-001 — Database Migration Specifications](DATABASE/SOP-DB-001_Migration_Specifications.md)
- [SOP-DB-002 — Deprecated Symbols Registry](DATABASE/SOP-DB-002_Deprecated_Symbols_Registry.md)
- [SOP-DB-003 — Schema Change Gate](DATABASE/SOP-DB-003_Schema_Change_Proposals.md)

### Procedures — Deployment (SOP-DEP)
- [SOP-DEP-001 — v2 Live-Test Runbook](DEPLOYMENT/SOP-DEP-001_Live_Test_Runbook.md)
- [SOP-DEP-002 — v2 Production Transition Runbook](DEPLOYMENT/SOP-DEP-002_Production_Transition_Runbook.md)

### Procedures — DevOps (SOP-DEV)
- [SOP-DEV-001 — Refactor Best Practices](DEVOPS/SOP-DEV-001_REFACTOR_BEST_PRACTICES.md)
- [SOP-DEV-002 — Canonical Domain Reconstruction Workflow](DEVOPS/SOP-DEV-002_CANONICAL_DOMAIN_RECONSTRUCTION_WORKFLOW.md)

### Procedures — Operations (SOP-OPS)
- [SOP-OPS-001 — Service Status and Incident Communication](OPERATIONS/SOP-OPS-001_SERVICE_STATUS_AND_INCIDENT_COMMUNICATION.md)

### Procedures — Security (SOP-SEC)
- [SOP-SEC-001 — Credentials and Identity Lookup Operations](SECURITY/SOP-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_OPERATIONS.md)

### Procedures — Testing (SOP-TEST)
- [SOP-TEST-001 — Validation Execution and Reporting](TESTING/SOP-TEST-001_Validation_Execution_And_Reporting.md)
- [SOP-TEST-002 — Accessibility Validation and PR Gate](TESTING/SOP-TEST-002_Accessibility_Validation_And_PR_Gate.md)
- [SOP-TEST-003 — Test Creation](TESTING/SOP-TEST-003_Test_Creation.md)

### Maps (MAP)
- [MAP-ADV-001 — Adversarial Evidence Documentation Protocol](../MAP/MAP-ADV-001_ADVERSARIAL_EVIDENCE_DOCUMENTATION_PROTOCOL.md)
- [MAP-CLASS-002 — Class Scope Normalization Target](../MAP/MAP-CLASS-002_CLASS_SCOPE_NORMALIZATION_TARGET.md)
- [MAP-CORE-001 — Domain to FEAT Capability Map](../MAP/MAP-CORE-001_DOMAIN_TO_FEAT_CAPABILITY_MAP.md)
- [MAP-UI-001 — Template to FEAT Wiring Map](../MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md)
- [MAP-UI-002 — Request Context and View Model Pipeline](../MAP/MAP-UI-002_REQUEST_CONTEXT_AND_VIEW_MODEL_PIPELINE.md)

### Reference (REF)
- [REF-API-001 — HTTP Interface Reference](../REFERENCE/REF-API-001_HTTP_INTERFACE_REFERENCE.md)
- [REF-TERM-001 — Developer Vocabulary](../REFERENCE/REF-TERM-001_DEVELOPER_VOCABULARY.md)
- [REF-TERM-002 — User Vocabulary](../REFERENCE/REF-TERM-002_USER_VOCABULARY.md)

### Principles (PRN)
- [PRN-PHL-001 — Design Principles, Philosophy, and Memory](../PRINCIPLES/PROJECT_PHILOSOPHY/PRN-PHL-001_Design_Principles_And_Project_History.md)
- [PRN-SNP-001 — Why Classroom Token Hub Does Not Implement SSO](../PRINCIPLES/SECURITY_AND_PRIVACY/PRN-SNP-001_Why_Classroom_Token_Hub_Does_Not_Implement_SSO.md)
- [PRN-SNP-002 — Trust-Based Account Recovery](../PRINCIPLES/SECURITY_AND_PRIVACY/PRN-SNP-002_Trust_Based_Account_Recovery.md)

### Related tracking records (unnumbered)

These are descriptive records, not registered documents. They are listed because the sections above
cite them and a reader following an argument needs to reach them.

- [Operations verifier policy decision package (2026-09-01)](../TRACKING/BATCH-B_OPERATIONS_VERIFIER_POLICY_DECISION_PACKAGE_20260901.md) — Operations freshness, aggregation, and evidence-registry owner decisions
- [V2 invariant verifier reconciliation (2026-08-31)](../TRACKING/V2_INVARIANT_VERIFIER_RECONCILIATION_20260831.md) — v1 economic checker to v2 verifier disposition

---

## VI. Legacy Specifications (v1 — Archived)

**Every document formerly listed in this section is archived.** This section previously read
"these legacy specifications remain active for reference during the transitional phase of the V2
port" and then listed roughly 90 links: the `ARC-*` architecture specs, the v1 `FEATURES/*` and
`DOMAINS/*` trees, the `SEC-*` audit corpus, and the v1 deployment/database SOPs. Of those links,
about two-thirds resolved to nothing at all — the paths pointed at repository-root directories
(`ARCHITECTURE/`, `FEATURES/`, `SECURITY/`) that have not existed since the v2 reorganization — and
the remainder pointed into `docs/archive/` without saying so.

An unlabelled link to archived material is indistinguishable from a citation of current authority
(`SOP-DOC-000` §V, *Citing archived material*), and a link that resolves to nothing is
indistinguishable from one that was satisfied. Enumerating them here reproduced both failures at
once, so the enumeration is removed rather than repaired.

The material itself is preserved and browsable:

| Archive location | Contents |
|---|---|
| `docs/archive/v1-architecture/` | Early v1 identity and core architectural specs (`ARC-*`) |
| `docs/archive/v1-docs/` | v1 security audits (`SEC-*`), deployment SOPs, `ARC-*` specs, `FEATURES/*`, `DOMAINS/*` |
| `docs/archive/v1-development/` | v1→v2 migration planning and legacy schema analysis |
| `docs/archive/v2-tracking-2026/` | Superseded v2 tracking, audits, and migration plans |
| `docs/archive/PHASE_PLANNING/` | Phase 3–5 roadmaps and store domain implementation tracking |
| `docs/archive/github-pages/` | Historical GitHub Pages landing site assets |

None of it is authority. For current architecture read `docs/INVARIANT/`; for current domain truth
read `docs/DOMAIN/`; for current procedures read the SOP sections above.

## VII. Informative Logs (LOG)

**The `LOG-*` namespace and the `docs/LOGS/` tree no longer exist.** They were removed on 2026-09-05
to prevent v1 material from being cited as authority. Nothing in this repository should link into
`docs/LOGS/`; the five entries formerly listed here resolved to deleted files.

Their surviving content lives at:

| Removed | Now |
|---|---|
| `LOG-REL-002_Changelog_Mirror` | Root `CHANGELOG.md` — maintained for developers and deliberately **not** published to the documentation site |
| `LOG-ARC-031_Project_History` | [PRINCIPLES/PROJECT_PHILOSOPHY/PRN-PHL-001](../PRINCIPLES/PROJECT_PHILOSOPHY/PRN-PHL-001_Design_Principles_And_Project_History.md) |
| `LOG-REL-003` / `LOG-REL-016` release notes | Root `CHANGELOG.md` version sections |
| `LOG-DEP-022_Scripts_Operations_Reference` | Not carried forward |

---

## VIII. Change Notes

**Version 3.4 (2026-09-19):**
- Completed the index. Version 3.3 listed 85 of the 131 numbered documents in the repository while
  §I claimed to be "the canonical master index of all formal documentation". The 46 absences
  included nearly every `FEAT-*` contract, `SOP-DB-001`, `SOP-DEP-001`/`002`, `SOP-SEC-001`,
  `SPEC-DES-001`, `SPEC-UI-001` and `INV-ARC-022` — that is, most of the procedures a contributor
  needs before touching the database, the design system, or a mutation path. Every link in 3.3
  resolved, so nothing here was visibly broken; the index was simply silent about a third of the
  corpus, which is the failure mode an index cannot show on its face.
- Renamed §V from "V2 Restructured Specifications" to "Registered Documents". The old title framed
  the list as the subset that had been ported, which is what licensed it to stay partial; there is
  no unported remainder to distinguish it from.
- Each entry now carries its document title, and sections are ordered by reference number.
- Moved the two unnumbered `docs/TRACKING/` records that §V cited into their own subsection, marked
  as descriptive rather than registered, per §II.
- `tests/dom/docs/test_documentation_index_complete.py` now fails when a numbered document exists
  without an entry here, so the gap cannot reopen silently.

**Version 3.2 (2026-09-06):**
- Audited every link in this index: 69 of 158 did not resolve. All 87 surviving links now resolve.
- Replaced §VI (`Legacy Specifications`) with an archive pointer. It had claimed ~90 v1 documents
  "remain active for reference"; two-thirds of those paths no longer existed and the rest pointed
  into `docs/archive/` unlabelled.
- Replaced §VII (`Informative Logs`) with a removal notice and supersession table. The `LOG-*`
  namespace and `docs/LOGS/` tree were deleted on 2026-09-05; all five entries were dead.
- Repaired five near-miss paths (`SOP-TEST-001/002/003`, the savings-interest spec, `FEAT-IDEN-001`)
  that pointed one directory level wrong or at a since-renamed file.
- Added the `PRN-PHL` section for `PRN-PHL-001`, which supersedes `LOG-ARC-031` and root
  `PROJECT_HISTORY.md`.

**Version 3.1 (2026-08-03):**
- Consolidated Phase 3-5 planning and store domain implementation logs into `docs/archive/PHASE_PLANNING/` (20 documents archived)
- Moved root-level phase/store execution docs to archive
- Consolidated `docs/SPECS/SPEC-STORE-001_*` into `docs/SPEC/` directory; removed empty `docs/SPECS/` directory
- Updated MAP-UI-001 to note store domain completion and removal of redemption_disposition FEAT
- Updated DEVELOPMENT.md to reflect store domain completion and current v2 status

---

## IX. Amendment

Revisions to this document must increment the version number, update the effective date, and remain consistent with the CTH documentation standard.
