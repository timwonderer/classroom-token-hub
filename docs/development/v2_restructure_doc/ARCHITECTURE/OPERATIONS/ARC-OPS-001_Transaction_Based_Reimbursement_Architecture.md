# ARC-OPS-001: Transaction-Based Reimbursement Architecture

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-OPS-001      | 2.0     | 2026-04-12     | 1.1        | Constitutional  |

## I. Purpose

This document defines the architectural rules for transaction-based reimbursement.

Its purpose is to ensure reimbursement behavior remains ledger-native, deterministic,
capability-governed, and structurally consistent with tenant isolation and explicit
command boundaries.

## II. Scope

This document applies to reimbursement flows that derive from an underlying debit
transaction.

It does not define non-monetary claim handling or unrelated insurance workflows.

## III. Authority Level

Constitutional (ARC Tier). Subordinate to:

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/INV-CORE-001_Capability_Based_Architecture_and_Authority_Model.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md`

## IV. Dependencies

- `docs/development/v2_restructure_doc/ARCHITECTURE/OPERATIONS/ARC-OPS-013_Money_Handling.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/OPERATIONS/ARC-OPS-015_Multi_tenancy_and_Join_Code_Interface.md`

## V. Core Reimbursement Rule

Reimbursement is a tenant-scoped monetary action that may occur only as an explicit
command derived from an existing debit transaction.

No reimbursement may exist without a linked expense and a request-time or job-time
capability decision grounded in current authoritative state.

## VI. Architectural Components

Transaction-based reimbursement spans the following architectural concerns:

- ledger truth for debits and reimbursements
- policy and enrollment state
- capability evaluation for claimability and payout permission
- reimbursement command execution
- claim lifecycle state

Each concern must remain inside its owned boundary.

## VII. Ledger Rule

All reimbursement money movement MUST be represented as ledger entries.

Architectural consequences:

- reimbursement does not edit balances directly
- reimbursement does not rewrite the source debit transaction
- reimbursement remains append-only and traceable
- reimbursement must maintain an explicit link to the source debit transaction

## VIII. Tenant Scope Rule

Reimbursement evaluation and execution MUST remain inside one tenant boundary.

Requirements:

- the source debit transaction must belong to the active tenant context
- claimability must be evaluated inside that same tenant context
- reimbursement creation must write into that same tenant context

No reimbursement flow may combine teacher-global, student-global, or cross-tenant state
as execution truth.

## IX. Capability Rule

Reimbursement permission must be expressed as capability evaluation, not route-local
conditionals.

Capability requirements:

- claim eligibility must be side-effect free
- payout permission must be side-effect free
- checks must evaluate explicit context only
- denial must be explainable

If multiple checks are required, they must compose under first-fail semantics.

## X. Command Rule

Reimbursement mutation must occur through an explicit command path only.

Command requirements:

- the command must run only after required capability checks pass
- the command must create the reimbursement ledger outcome idempotently
- the command must update claim lifecycle state consistently with the monetary outcome
- the command must not mutate unrelated domain state as a hidden side effect

## XI. Determinism Rule

For a given source transaction, policy state, enrollment state, and tenant context, the
eligibility and payout result must be deterministic.

Deterministic reimbursement requires:

- stable classification of the source debit transaction
- explicit policy constraints
- explicit enrollment state
- explicit cap calculations
- reproducible linkage between claim and reimbursement outcome

## XII. One-To-One Linkage Rule

Transaction-based reimbursement must preserve unambiguous linkage.

Architectural requirements:

- a claim must reference one source debit transaction
- a reimbursement outcome must reference the debit transaction it compensates
- duplicate payout for the same claimable event must be prevented by command design and
  supporting data constraints

## XIII. Cross-Domain Boundary Rule

Reimbursement may depend on multiple domains, but no domain may directly mutate another
under the guise of reimbursement handling.

Architectural consequences:

- policy state may inform reimbursement decisions without owning ledger mutation
- ledger owns reimbursement money movement without owning policy rules
- feature flows may orchestrate checks and commands without becoming the source of claim
  logic

## XIV. Read Purity Rule

Reimbursement visibility and claim selection paths must be pure reads.

The following are forbidden in read paths:

- auto-creation of claims
- auto-payment on view
- hidden state cleanup that changes reimbursement eligibility
- mutation triggered by rendering claim options

## XV. Prohibited Patterns

The following are forbidden:

- reimbursement without source debit linkage
- direct balance edits instead of reimbursement ledger entries
- route-local eligibility logic duplicated across student, admin, and automation paths
- claim selection paths that mutate claim or payout state
- cross-tenant reimbursement evaluation
- reimbursement commands with hidden non-reimbursement side effects

## XVI. Architectural Consequences For Later Layers

This document constrains the rest of the system as follows:

- DOM work must expose reimbursement capability checks and reimbursement commands as
  explicit domain contracts
- FEAT work must orchestrate reimbursement using those contracts instead of embedding its
  own business rules
- money handling and tenant isolation rules remain mandatory throughout reimbursement
  behavior

## XVII. Amendment

Revisions to this document require a version increment, an updated Effective Date, and
continued consistency with the locked invariant and foundation documents named above.
