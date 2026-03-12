# DOM-ECON-001: Economy Balance Checker

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-ECON-001     | 1.1     | 2026-03-08     | DOM-ECON-001 v1.0 | Constitutional |

## I. Purpose

This document defines the constitutional role of the Economy Balance Checker as the authoritative CWI-based validation and recommendation engine for teacher-facing economy configuration workflows.

## II. Scope

This document governs the behavior of the Economy Balance Checker across economy-health analysis, real-time form validation, policy-aware recommendations, rebalance previews, and teacher-facing guidance for rent, store pricing, insurance, and fines.

## III. Authority Level

Constitutional (DOM Tier). This document is subordinate to `INV-CORE-000_Core_Invariants.md`, `DOM-CORE-000_Domain_Foundation.md`, and `DOM-ECON-002_Economy_Specification.md`.

## IV. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`
- `DOM-ECON-002_Economy_Specification.md`

## V. Core Responsibilities

The Economy Balance Checker shall serve as the single recommendation engine for teacher-facing economy validation.

It shall:

1. calculate CWI from payroll settings
2. normalize settings to weekly equivalents before comparison
3. evaluate configuration against the active policy mode
4. generate warnings, ranges, and recommended values
5. execute budget survival validation
6. provide data used by rebalance previews and policy alignment status

No teacher-facing rebalance workflow shall reimplement independent ratio logic outside the checker.

## VI. CWI Contract

### 1. Source of Truth

CWI shall be calculated from active payroll settings for the relevant teacher and block.

### 2. Expected Weekly Hours

`PayrollSettings.expected_weekly_hours` shall remain the authoritative input for balance checking. This field shall be used for CWI validation only and shall not alter payroll earnings calculations.

### 3. Block Scope

If a teacher has multiple blocks, the checker shall evaluate the block-specific payroll and rent context rather than falling back to an unrelated block.

## VII. Policy-Aware Recommendation Model

The checker shall read the classroom's active economy policy mode and apply the corresponding bands from `DOM-ECON-002_Economy_Specification.md`.

### 1. Rent Guidance

The checker shall surface rent warnings and recommended ranges using the active policy mode's weekly rent burden band, converted into the teacher's configured rent frequency for display.

### 2. Store Guidance

The checker shall surface policy-aware pricing guidance for all store tiers:

- Basic
- Standard
- Premium
- Luxury

### 3. Insurance Guidance

The checker shall surface policy-aware insurance guidance for all of the following:

- premium
- maximum claim amount
- maximum payout per period
- waiting period days

### 4. Fine Guidance

The checker shall surface policy-aware fine ranges tied to weekly CWI.

## VIII. Validation Surfaces

The checker shall support both full-analysis and single-field validation.

### 1. Economy Health

The full analysis surface shall provide:

- current CWI
- active policy mode
- balance warnings grouped by severity
- policy-aware recommendations
- budget survival status
- alignment context used by rebalance workflows

### 2. Real-Time Settings Validation

The single-field validation surface shall remain available on teacher settings pages.

At minimum, the following surfaces shall remain supported:

- rent settings
- insurance policy creation and editing
- store item pricing
- payroll fine configuration

### 3. Insurance Form Guidance

Insurance validation shall return recommendations sufficient for the UI to show tips and warnings for:

- premium range
- maximum claim range
- period cap range
- waiting period range

## IX. Warning Semantics

The checker shall classify outputs using consistent severity labels:

- `critical`
- `warning`
- `info`

Severity shall reflect deviation from the active policy band's lower or upper boundary and shall not silently collapse materially unsafe configurations into informational output.

## X. Rebalance Relationship

The rebalancer shall consume checker outputs instead of duplicating ratio logic.

The checker shall therefore provide the recommendation data necessary to construct before/after previews for supported categories.

## XI. Invariants

1. Historical transactions shall remain immutable.
2. Existing frozen insurance snapshots shall remain immutable.
3. Policy mode shall affect recommendations and future-facing configuration only.
4. The checker shall remain block-aware and tenant-safe.
5. The checker shall remain the single source of truth for policy-aware economy guidance.

## XII. Amendment

Revisions to this document shall:

1. increment the version number
2. update the Effective Date
3. maintain consistency with `DOM-ECON-002_Economy_Specification.md`
4. preserve compatibility with higher-authority invariants
