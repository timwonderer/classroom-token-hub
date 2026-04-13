# V2 Realignment Checklist

**Last Updated:** 2026-04-12  
**Status:** Active planning document  
**Purpose:** Redefine the v2 execution checklist around the locked formal specification set so the application can be rebuilt toward structural integrity, not merely documentation consistency.

## Decision

As of 2026-04-12, the prior project sequencing captured in the legacy launch checklist is paused for this realignment track.

The active v2 program is now:

1. Anchor v2 to the locked INV and ARC specifications.
2. Write the full ARC-layer document set intentionally and in dependency order.
3. Use those ARC documents to define the next implementation checklist only after the architecture layer is coherent.
4. Treat the resulting ARC layer as the structural control surface for the entire app.

Until that ARC realignment is complete, the previous launch-project checklist is not the active execution plan for this track.

## Locked Authority For This Phase

The following documents are the governing references for this realignment:

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/INV-CORE-001_Capability_Based_Architecture_and_Authority_Model.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/ARC-CORE-000_EXECUTION_MODEL.md`
- `docs/development/V2_CAPABILITY-BASED_ARCHITECTURE_REBUILD.md`

## Scope Boundary

### In Scope

- Redefine the v2 checklist and planning sequence.
- Write the full ARC-level doc set in the realignment workspace.
- Use the audit and current repo shape as the evidence base for those ARC rewrites.
- Capture architectural priorities before reopening code implementation work.
- Define the structural rules needed to restore whole-app integrity across request flow, authority, mutation, data scoping, and observability.

### Out Of Scope

- Editing locked INV docs.
- Editing canonical ARC, DOM, FEAT, SOP, or LOG docs during this parking phase.
- Resuming old checklist projects directly.
- Code changes, migrations, or runtime behavior changes during this planning phase.

## Working Rules

- Every ARC rewrite must derive directly from the locked INV/ARC authority above.
- Every ARC rewrite must be grounded in the current repo shape, not an imagined clean-room architecture.
- The audit is a diagnostic input, not the authority source.
- We do not normalize current violations into architectural truth.
- We do not hide current violations by writing vague docs.
- We are designing for structural integrity of the running system, not paper alignment of the docs.
- When current code and target architecture diverge, the ARC doc must state the intended rule clearly enough to drive a later implementation plan.
- Sequence matters: upstream ARC docs must be settled before downstream ARC docs are rewritten.
- We are not optimizing this track for backward compatibility.

## ARC Document Inventory

This realignment track must produce a complete parked draft set for every ARC document
currently defined under `ARC-CORE-000`.

### ARC Core

- [x] `ARC-CORE-000_Architecture_Foundation.md`

### ARC Operations

- [x] `ARC-OPS-000_Operational_Constraints.md`
- [x] `ARC-OPS-001_Transaction_Based_Reimbursement_Architecture.md`
- [x] `ARC-OPS-005_Api_Reference.md`
- [x] `ARC-OPS-007_Database_Schema.md`
- [x] `ARC-OPS-012_Datetime_Handling_Specification.md`
- [x] `ARC-OPS-013_Money_Handling.md`
- [x] `ARC-OPS-015_Multi_tenancy_and_Join_Code_Interface.md`

### ARC Identity

- [x] `ARC-IDEN-001_Admin_Identity_Handling.md`
- [x] `ARC-IDEN-002_Account_Recovery.md`

### ARC Sysadmin

- [x] `ARC-SYS-001_Sysadmin_Interface.md`
- [x] `ARC-SYS-002_Deterministic_Analytics_Alerting_Pipeline.md`

### Inventory Rule

- Every document above must have a parked realignment draft before this phase is considered complete.
- No canonical ARC document is edited until the parked set is internally coherent.
- Dependency order still governs the writing sequence; inventory completeness governs phase completion.

## Realignment Strategy

### Phase 0: Checklist Reset And Control Boundaries

- [x] Pause the old launch-project sequencing for this realignment track.
- [x] Establish the locked INV/ARC documents as the governing source for this phase.
- [x] Restrict working-document edits for this phase to the realignment workspace.
- [x] Define the exact ARC rewrite order before any downstream ARC text is rewritten.

### Phase 1: Core ARC Translation

Goal: establish the repo-facing ARC spine that all remaining ARC docs must descend from.

- [x] Draft a rewritten `ARC-CORE-000` in the realignment workspace.
- [x] Ensure the rewritten `ARC-CORE-000` mirrors the locked execution model authority, terminology, and enforcement sequence.
- [x] Make `ARC-CORE-000` explicitly define how the repo ARC namespace derives from:
  - request context construction
  - capability evaluation
  - allow/deny resolution
  - single-command mutation
  - response return
- [x] Lock the ARC/DOM/FEAT separation in the foundation text:
  - ARC defines allowed interactions
  - DOM defines bounded modules and owned truth
  - FEAT defines specific action orchestration

Why first:

- Every later ARC document must inherit its authority from this execution model.
- The audit’s biggest failures are execution-model failures: write-on-read, unscoped decisions, recomputed state, and weak command boundaries.
- Structural integrity starts here because the execution model determines whether the app can enforce consistent behavior at runtime.

### Phase 2: Tenant And Authority Boundary Docs

Goal: lock down the documents that define scope, actor boundaries, and who may act inside a request.

Priority order:

- [x] `ARC-OPS-015_Multi_tenancy_and_Join_Code_Interface.md`
- [x] `ARC-IDEN-001_Admin_Identity_Handling.md`
- [x] `ARC-SYS-001_Sysadmin_Interface.md`

Required outcomes:

- [x] `ARC-OPS-015` aligns with single-tenant request scope, explicit context, no phantom scope access, and membership-by-existence.
- [x] `ARC-IDEN-001` defines actor identity and authority boundaries without drifting into feature logic.
- [x] `ARC-SYS-001` aligns with the invariant that system administrators do not access or alter `join_code`-scoped tenant data.

Why this comes second:

- These docs establish the authority and scope constraints that all command, finance, API, and observability docs must obey.
- The audit shows current leakage around `teacher_id`, unscoped balances, and tenant-boundary confusion. Those have to be closed architecturally before lower-level docs are rewritten.
- If these boundaries stay ambiguous, the rest of the app cannot become structurally sound even if individual features are rewritten correctly.

### Phase 3: Mutation, Money, And Cross-Domain Execution Docs

Goal: define how mutation is allowed to happen once request scope and actor authority are fixed.

Priority order:

- [x] `ARC-OPS-013_Money_Handling.md`
- [x] `ARC-OPS-001_Transaction_Based_Reimbursement_Architecture.md`
- [x] `ARC-SYS-002_Deterministic_Analytics_Alerting_Pipeline.md`

Required outcomes:

- [x] `ARC-OPS-013` is now a constitutional money-handling document rather than a placeholder.
- [x] `ARC-OPS-013` aligns with deterministic ledger authority, side-effect boundaries, and no recomputation outside domain authority.
- [x] `ARC-OPS-001` now frames reimbursement around capability-first execution and explicit command boundaries.
- [x] `ARC-SYS-002` now defines aggregate observability in a way that preserves isolation and avoids hidden cross-tenant access patterns.

Why this comes third:

- The audit’s highest-risk behavioral failures are concentrated in money movement, write-on-read behavior, and cross-domain coupling.
- These docs must be rewritten after scope and authority are fixed, but before API/schema/supporting documents are updated.
- This is the layer where architectural weakness becomes user-visible corruption, so it must be defined before implementation resumes.

### Phase 4: Supporting ARC Contract Docs

Goal: update the remaining ARC documents so they reflect the now-settled execution model rather than inventing parallel rules.

Priority order:

- [x] `ARC-OPS-005_Api_Reference.md`
- [x] `ARC-OPS-007_Database_Schema.md`
- [x] `ARC-OPS-000_Operational_Constraints.md`
- [x] `ARC-OPS-012_Datetime_Handling_Specification.md`
- [x] `ARC-IDEN-002_Account_Recovery.md`

Required outcomes:

- [x] API documentation now describes execution contracts that derive from the rewritten ARC layer.
- [x] Schema documentation now reflects canonical identifiers, coexistence rules, and request-scoped authority without flattening transitional structures into equal authority.
- [x] Operational and datetime documents have been rewritten to remain subordinate and non-conflicting.
- [x] Account recovery has been reframed so it obeys the same explicit scope, identity, and command rules as the rest of the system.

Why last:

- These docs should consume architectural decisions, not make them.
- Rewriting them earlier would create churn and likely force a second rewrite.

### Phase 5: ARC Set Completion Review

Goal: confirm the parked ARC set is complete and internally consistent before deriving
the app rebuild plan.

- [x] Every ARC document listed in the inventory has a parked draft.
- [x] Each parked ARC document derives cleanly from the parked `ARC-CORE-000`.
- [x] Cross-references between parked ARC docs do not conflict after coherence review.
- [x] No parked ARC doc preserves legacy or mixed-boundary behavior as target architecture.
- [x] The parked ARC set is sufficient to drive DOM and FEAT writing later.

## Doc-Writing Standard For This Realignment

Every ARC rewrite in this phase must do all of the following:

- [ ] Name the locked upstream authority it derives from.
- [ ] State the cross-domain architectural concern it governs.
- [ ] Anchor its rules in the current repo shape where relevant.
- [ ] Avoid feature-level implementation detail unless necessary to define the architectural boundary.
- [ ] State prohibitions clearly, especially where the audit found recurring violations.
- [ ] Be written so a later implementation checklist can be derived from it without reinterpretation.
- [ ] Define rules that can actually constrain future code structure, not just describe preferred behavior.

## Repo-Grounded Priority Signals From The Audit

The following findings are the main drivers of rewrite order:

- [ ] Write-on-read behavior must be addressed architecturally before endpoint or feature docs are trusted.
- [ ] Capability checks must become first-class architectural primitives, not route-local conditionals.
- [ ] `join_code` / `class_id` request scope must replace teacher-global or unscoped decision paths.
- [ ] Domain authority must be documented tightly enough to prevent cross-domain mutation patterns.
- [ ] Sysadmin observability must remain aggregate and non-tenant-invasive.
- [ ] The rewritten ARC layer must be strong enough to support a later structural rebuild plan for the app, not just a doc cleanup pass.

## Exit Criteria For This Planning Phase

- [x] The ARC rewrite order is accepted and stable.
- [x] The target ARC documents are grouped by dependency, not convenience.
- [x] The checklist clearly separates architecture-definition work from later implementation work.
- [x] The checklist makes structural integrity of the full app the reason for this phase, not just formal doc alignment.
- [x] Every ARC document named by `ARC-CORE-000` has a parked draft in the realignment workspace.
- [x] No canonical docs are changed as part of this parked drafting phase.
- [ ] A follow-on implementation checklist can be generated directly from the rewritten ARC layer once complete.

## Immediate Next Step

- [ ] Derive the application rebuild checklist from the stabilized parked ARC set.
