# DOM-CLASS-002: Class Economy Governance

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| DOM-CLASS-002 | 2.1 | 2026-10-03 | 2.0 | Constitutional |

## I. Purpose

This document defines the class economy foundation for Classroom Token Hub (CTH).

It derives its authority from `DOM-CLASS-001` and provides the class-economy facts that `DOM-CLASS-003` and the `SPEC-ECON-*` documents build on.

This document establishes:
- the class economy is CWI-relative,
- the class economy supports `tight`, `default`, and `comfortable` modes,
- class economy configuration belongs to Class Configuration,
- rebalance actions are class-economy events,
- bank-related businesses are part of class configuration,
- behavioral calculations are defined by the relevant `SPEC-ECON-*` documents.

## II. Scope

This document governs:
- class economic posture,
- supported economic mode,
- class-wide economic configuration facts,
- economic rebalance boundaries,
- class-level economic inputs consumed by downstream specs and features.

This document does not govern:
- interest formulas,
- compounding formulas,
- accrual timing,
- solvency math,
- analytics metrics,
- visibility behavior,
- or other execution semantics.

The exact specification for interest and compounding rules as well as overdraft behavior belongs in SPEC-level documentation.

## III. Authority Level

Constitutional (DOM Tier).

Subordinate to:
- `INV-CORE-000`
- `DOM-CORE-000`
- `INV-ARC-015`

No FEAT, SOP, runtime workflow, API surface, or UI behavior may override the class economy facts established here.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

This dependency list introduces no DOM-to-DOM execution dependency. The pre-existing class-governance ownership references below describe configuration authority; FEATs coordinate all runtime cross-domain access.

## V. Class Economy Facts

`DOM-CLASS-002` establishes these class economy facts:
- the class economy is CWI-relative,
- the class economy has exactly three supported modes,
- the class economy can be rebalanced,
- class-level economic configuration is stored by `DOM-CLASS-001`,
- execution semantics are owned by the relevant SPEC and FEAT layers.

`DOM-CLASS-002` does not define the formulas or behavioral rules for:
- CWI derivation,
- savings interest,
- policy calibration,
- solvency,
- or analytics.

## VI. Relationship to Other Documents

`DOM-CLASS-001` owns:
- class identity,
- class configuration storage,
- and the `economic-engine` table.

`DOM-CLASS-003` owns:
- economics policy lineage,
- policy version state,
- and policy activation semantics.

`SPEC-ECON-001` owns:
- savings interest accrual,
- disbursement,
- compounding,
- eligibility,
- and scheduling behavior.

`SPEC-ECON-002` owns:
- policy visibility,
- future-law disclosure,
- and operational disclosure behavior.

## VII. Shared Charge-Funding Rule

This class-economy contract explicitly incorporates `SPEC-ECON-003` §4.5.1.1A. Class-scoped overdraft protection applies universally to lawful charges and deductions, including penalties and payroll corrections: savings funds the exact checking shortfall only when it can cover the entire shortfall; otherwise savings remains unchanged and checking may become negative. This grants no independent business authorization for a charge. Own-account transfers remain sufficient-funds operations without protection or fees. Failed-agreement fee applicability remains separate (§4.5.1.1), and payroll correction carries no NSF fee, new obligation, or deferred deduction. FEAT orchestration composes the owning configuration and monetary authorities; no domain directly invokes another domain.

Authority: `INV-CORE-000` §III.1,3–4, `INV-ARC-006` §V, `INV-ARC-009` §V, and `INV-ARC-021` §V, VII. **2.1 (2026-10-03)** supersedes 2.0's unspecified funding behavior with this incorporated technical rule, without changing interest or fee pricing.

## VIII. Amendment

Revisions to this document must increment the version number, update the effective date, and remain consistent with `DOM-CLASS-001`.
