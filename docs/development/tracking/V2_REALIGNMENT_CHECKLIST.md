# V2 Realignment Checklist

**Last Updated:** 2026-04-13  
**Status:** Active planning document  
**Purpose:** Align the parked v2 realignment workspace to the new authority model where
`INV` contains both `CORE` and `ARC`, `DOM` and `FEAT` are the remaining normative
layers, and all previous standalone `ARC-*` architectural docs are removed from this
level.

## Decision

As of 2026-04-13:

1. Standalone `ARC` is no longer a normative layer.
2. Architectural execution rules now live in the `INV-ARC` namespace under `INV`.
3. Only `INV-CORE` and `INV-ARC` docs belong at this top normative level.
4. `DOM` and `FEAT` remain normative downstream layers.
5. Anything else at this level is informative or does not apply.

## Locked Authority For This Phase

The governing documents for this namespace realignment are:

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/INV-CORE-001_Capability_Based_Architecture_and_Authority_Model.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/INV-ARC-000_EXECUTION_MODEL.md`

## Scope Boundary

### In Scope

- update the parked realignment workspace to the new `INV` authority model
- retain only the `INV-CORE` and `INV-ARC` doc sets at this level
- remove deprecated parked `ARC-*` thematic docs from this namespace
- materialize the permitted `INV-ARC` doc set that belongs at this level
- prepare the workspace to derive `DOM` and `FEAT` from the stabilized `INV` layer

### Out Of Scope

- editing canonical repo docs outside the parked realignment workspace
- deriving `DOM` docs in this step
- deriving `FEAT` docs in this step
- code changes, migrations, or runtime behavior changes

## Normative Layer Model

The normative hierarchy for the parked v2 realignment workspace is now:

1. `INV-CORE`
2. `INV-ARC`
3. `DOM`
4. `FEAT`

There is no independent `ARC` layer anymore.

## Allowed Top-Level Doc Set

Only the following doc families belong at this level:

### INV-CORE

- [x] `INV-CORE-000_Core_Invariants.md`
- [x] `INV-CORE-001_Capability_Based_Architecture_and_Authority_Model.md`

### INV-ARC

- [x] `INV-ARC-000_EXECUTION_MODEL.md`
- [x] `INV-ARC-001_Scoped_Request_Context.md`
- [x] `INV-ARC-002_No_Implicit_Global_Access.md`
- [x] `INV-ARC-003_Scoped_Capability_Evaluation.md`
- [x] `INV-ARC-004_Cross_Tenant_Isolation.md`
- [x] `INV-ARC-005_No_PII_Leakage_in_Execution_Layer.md`
- [x] `INV-ARC-006_Command_Boundary_for_Mutation.md`
- [x] `INV-ARC-007_GET_Must_Be_Pure.md`
- [x] `INV-ARC-009_Domain_Authority_for_State.md`
- [x] `INV-ARC-010_Explicit_Context_Switching.md`
- [x] `INV-ARC-011_No_Phantom_Scope_Access.md`
- [x] `INV-ARC-012_Hard_Deletion_Enforcement.md`
- [x] `INV-ARC-013_Membership_by_Existence.md`
- [x] `INV-ARC-014_No_Label_Based_Logic.md`

## Removed From This Level

The following parked doc families no longer belong in this normative namespace:

- `ARC-CORE-*`
- `ARC-IDEN-*`
- `ARC-OPS-*`
- `ARC-SYS-*`

Those thematic docs may later reappear only if reclassified under `DOM`, `FEAT`, or an
informative namespace.

## Realignment Outcomes Completed

- [x] The parked workspace reflects the new authority model where `INV-ARC` replaces
  standalone `ARC`.
- [x] Deprecated parked `ARC-*` docs have been removed from this level.
- [x] The permitted `INV-ARC` doc set has been materialized in the parked workspace.
- [x] The top normative layer is now restricted to `INV-CORE` and `INV-ARC`.

## Exit Criteria For This Phase

- [x] The parked namespace matches the new authority model.
- [x] Only allowed top-level normative docs remain at this layer.
- [x] Deprecated parked `ARC-*` docs are no longer part of this level.
- [x] The parked `INV` layer is ready to drive `DOM` and `FEAT` planning.

## Immediate Next Step

- [ ] Derive the application rebuild checklist from the stabilized `INV-CORE` and
  `INV-ARC` set, then begin `DOM` planning from that authority base.
