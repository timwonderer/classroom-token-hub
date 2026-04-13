# ARC-OPS-013: Money Handling

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-OPS-013      | 2.0     | 2026-04-12     | 1.0        | Constitutional  |

## I. Purpose

This document defines the architectural rules for money representation, money
computation, ledger-derived balances, and monetary mutation in Classroom Token Hub.

Its purpose is not merely numeric correctness. Its purpose is to ensure that all money
behavior remains deterministic, tenant-scoped, traceable, and compatible with the
capability-governed execution model.

## II. Scope

This document applies to:

- all monetary values
- ledger entries and reversals
- cached balances and settlement outputs
- money-related capability checks
- money-related domain commands
- money serialization at system boundaries

## III. Authority Level

Constitutional (ARC Tier). Subordinate to:

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/INV-CORE-001_Capability_Based_Architecture_and_Authority_Model.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md`

## IV. Dependencies

- `docs/development/v2_restructure_doc/ARCHITECTURE/OPERATIONS/ARC-OPS-015_Multi_tenancy_and_Join_Code_Interface.md`

## V. Core Money Rule

All money behavior MUST be derived from authoritative ledger state inside a single
tenant boundary.

Money truth may be cached for performance, but cache state does not replace ledger
authority.

## VI. Representation Rules

Money values must be represented using exact decimal-safe forms.

Architectural requirements:

- internal monetary arithmetic must use `Decimal` or exact integer-cent forms
- floating-point arithmetic must not be used as execution truth
- monetary zero defaults must use exact monetary representations
- persistence and comparison must use quantized two-decimal currency semantics where
  applicable

## VII. Ledger Authority

The ledger is the sole authority for monetary mutation.

Architectural consequences:

- all monetary movement must appear as ledger entries
- reversal occurs by counter-entry, not deletion or silent overwrite
- prior monetary outcomes must remain reproducible from historical ledger state and
  configuration at execution time

No layer may treat derived balances as a substitute for ledger history.

## VIII. Scoped Balance Rule

All balances used for runtime decisions MUST be tenant-scoped.

Architectural requirements:

- no money-related capability check may use unscoped balance state
- no route or feature action may authorize spending or transfer from balance state that
  is not explicitly bound to the active tenant
- teacher-global or actor-global balance aggregation must not be used as request-time
  execution truth

This means balance access must always be explicit about tenant scope.

## IX. Cached Balance Rule

Cached balances are performance artifacts, not independent monetary truth.

Architectural requirements:

- cache state must derive from authoritative ledger activity
- cache state must remain tenant-scoped
- cache refresh or settlement must not occur implicitly inside read-only request paths
- cache divergence must be treated as a correctness defect, not a normal operating mode

If a balance cache exists, it must preserve ledger semantics rather than invent new
monetary state.

## X. Read Purity For Money

Read paths involving money must be pure.

The following are forbidden in read paths:

- settlement triggered as a side effect of balance inspection
- automatic posting caused by rendering a page
- money mutation during analytics, templates, or status views
- repair behavior hidden behind reads

Money correction, settlement, and posting must happen in explicit command or job paths.

## XI. Monetary Capability Rules

Money-related capability checks are architectural authorization decisions and must obey
all ARC rules.

Requirements:

- checks must evaluate current tenant-scoped monetary state
- checks must be side-effect free
- checks must return deterministic allow or deny outcomes
- checks must not instantiate ledger entries directly

Capability checks may read ledger-derived or cache-derived scoped values, but may not
change them.

## XII. Monetary Command Rules

Monetary mutation must occur only through explicit domain commands.

Command requirements:

- command input must include explicit tenant context
- command execution must write append-only ledger outcomes
- idempotency must be enforced where retries or duplicate submissions are possible
- command boundaries must be observable and auditable

Feature code must not construct ad hoc monetary mutation paths outside these commands.

## XIII. Serialization Boundaries

Money may cross system boundaries only as presentation or transport values.

Architectural requirements:

- serialized money is not execution truth
- any inbound money used for arithmetic must be normalized before use
- presentation formatting must not leak back into business logic

## XIV. Prohibited Patterns

The following are forbidden:

- float-based execution truth
- unscoped balance checks
- implicit settlement on read
- direct balance mutation without ledger entry
- silent mutation or deletion of financial history
- feature-layer monetary mutation outside explicit domain commands

## XV. Architectural Consequences For Later Layers

This document constrains the rest of the system as follows:

- DOM documents must define monetary truth through ledger-owned and tenant-scoped state
- FEAT documents must treat balances as queried truth, not recomputed route-local data
- reimbursement, purchase, transfer, payroll, rent, and analytics paths must all obey
  the same scoped money rules

## XVI. Amendment

Revisions to this document require a version increment, an updated Effective Date, and
continued consistency with the locked invariant and foundation documents named above.
