# V2 Realignment Checklist

**Last Updated:** 2026-04-25  
**Status:** Baseline complete; downstream derivation paused while runtime stabilization is active  
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

- `docs/development/v2_restructure_doc/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/development/v2_restructure_doc/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/development/v2_restructure_doc/INVARIANT/ARCHITECTURE/INV-ARC-000_EXECUTION_MODEL.md`

## Current Status Note (2026-04-25)

- This checklist's structural realignment outcomes remain complete.
- The remaining unchecked step is still valid, but execution is sequenced after current v2 runtime hardening and launch-readiness stabilization.

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

- [x] `INV-CORE-000_CORE_INVARIANTS.md`
- [x] `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`

### INV-ARC

- [x] `INV-ARC-000_EXECUTION_MODEL.md`
- [x] `INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`
- [x] `INV-ARC-002_NO_IMPLICIT_GLOBAL_ACCESS.md`
- [x] `INV-ARC-003_SCOPED_CAPABILITY_EVALUATION.md`
- [x] `INV-ARC-004_CROSS_TENANT_ISOLATION.md`
- [x] `INV-ARC-005_NO_PII_LEAKAGE_IN_EXECUTION_LAYER.md`
- [x] `INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`
- [x] `INV-ARC-007_GET_MUST_BE_PURE.md`
- [x] `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- [x] `INV-ARC-010_EXPLICIT_CONTEXT_SWITCHING.md`
- [x] `INV-ARC-011_NO_PHANTOM_SCOPE_ACCESS.md`
- [x] `INV-ARC-012_HARD_DELETION_ENFORCEMENT.md`
- [x] `INV-ARC-013_MEMBERSHIP_BY_EXISTENCE.md`
- [x] `INV-ARC-014_NO_LABEL_BASED_LOGIC.md`

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
