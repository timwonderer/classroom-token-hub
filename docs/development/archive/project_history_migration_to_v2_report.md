# Project History Report: Migration Timeline and V2 Restructuring Alignment

## Scope and Method
This report reconstructs project history from two evidence sets:

1. `migrations/versions/*.py` (revision graph, `Create Date`, `down_revision`, and `upgrade()` behavior).
2. V2 restructuring authority documents from `origin/codex/v2.0`, especially:
   - `docs/development/v2_restructure_doc/DOMAIN/DOM-CORE-000_DOMAIN_FOUNDATION.md`
   - `docs/development/v2_restructure_doc/DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md`
   - `docs/development/v2_restructure_doc/DOMAIN/DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`
   - `docs/development/v2_restructure_doc/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
   - `docs/development/v2_restructure_doc/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
   - `docs/development/v2_restructure_doc/INVARIANT/ARCHITECTURE/INV-ARC-000_EXECUTION_MODEL.md`

No application code, tests, or external narrative sources were used to build this history.

---

## Executive Summary
The migration history shows a product that evolved rapidly from a compact classroom economy schema into a multi-domain system with increasingly strict tenancy, identity, financial integrity, and observability controls. As feature velocity increased, schema branching and corrective migrations became frequent. V2 responds to this historical pattern by formalizing architectural law: domain ownership, FEAT-only mutation, canonical runtime schema authority, and invariant-governed execution.

---

## Migration Timeline (Reconstructed)

## Phase 0: Baseline Foundation and Early Normalization (Jul-Oct 2025)
- Root schema established around admins, students, purchases, tap sessions, and transactions.
- `system_admins` introduced early, signaling separation of operational authority from classroom actors.
- Tap/session model normalized: `tap_events` added, legacy `tap_sessions` removed.
- Store model shifted from older purchase flow toward `store_items` and `student_items`.
- Early data security hardening appeared:
  - student first-name encryption,
  - corrective data migration for incorrectly encrypted rows.
- Hall pass runtime model introduced and integrated with broader flow.

Historical signal: this phase establishes domain surfaces but still carries first-generation coupling and broad table responsibilities.

## Phase 1: Feature Expansion and Branch Convergence Pressure (Nov 2025)
- Major domain growth occurred in parallel:
  - rent,
  - insurance,
  - payroll,
  - banking,
  - hall-pass settings,
  - user/support reporting,
  - feature settings and onboarding.
- Multiple merge migrations indicate concurrent tracks landing into shared schema.
- Tenancy pressure became explicit:
  - more `teacher_id` propagation,
  - `teacher_blocks` introduced,
  - class-scoping fields spread across settings and policy tables.
- Insurance moved quickly through policy identity, payout controls, tiering, and product settings.

Historical signal: high delivery throughput, but scope/authority semantics were still being patched into existing structures.

## Phase 2: Identity, Recovery, and Governance Hardening (Dec 2025)
- Enum/type repair chain for deletion requests and related statuses.
- Student lifecycle and profile migration tracking fields added.
- Recovery architecture expanded:
  - verification and recovery request tables,
  - partial recovery state,
  - hashed DOB strategy.
- Passkey credential model iterated for admin/system-admin authentication.
- Support operations matured:
  - issue categories,
  - issue state history,
  - resolution actions,
  - announcement capabilities.
- Join-code propagation widened to more tables.

Historical signal: correctness and security remediation became a recurring development theme, not a one-time task.

## Phase 3: Financial Precision and Class-Scope Refactor (Jan-Feb 2026)
- Financial correctness tightened:
  - transaction amount precision migration,
  - ledger/settlement model introduction,
  - stronger traceability fields.
- A large timezone and scope refactor rewired broad portions of runtime schema:
  - class economy primitives (`class_economies`, `class_memberships`, aliases),
  - join-code foreign-key rewiring,
  - actor membership links for execution traces.
- Rent and insurance received deeper structural updates:
  - coverage periods,
  - item typing/allocation,
  - snapshot/frozen policy semantics.
- Identity hardening continued:
  - admin identity revamp,
  - username hashing,
  - encrypted display-name storage.

Historical signal: this phase marks transition from feature accumulation to architectural consolidation.

## Phase 4: Canonical Anchoring, Correlation, and Policy-Oriented Runtime (Feb-Apr 2026)
- Join-code strategy became explicit and normalized:
  - broad backfill of `join_code` across class-scoped tables,
  - `join_codes` anchor table introduced,
  - `join_code_id` foreign-key propagation and mapping.
- Observability and operations strengthened:
  - request trace tables,
  - correlated error/ticket context pack,
  - richer audit correlation IDs.
- Execution safety and replayability improved:
  - transaction idempotency key,
  - transfer correlation ID.
- Policy-focused schema evolution continued:
  - economy policy mode fields,
  - modularized insurance product structure,
  - economy snapshot + analysis payload,
  - additional insurance and rent policy controls.

Historical signal: runtime behavior moved toward explicit policy governance and auditable execution context.

---

## V2 Restructuring Narrative
The V2 restructure documents define a constitutional architecture that codifies lessons from the migration history.

### 1. Domain Authority Becomes Explicit Law
`DOM-CORE-000` and `DOM-CORE-001` define domains as logical mutation boundaries with single-table ownership and no shared write authority by convenience. This directly addresses historical drift where cross-cutting features repeatedly touched overlapping schema with corrective follow-up migrations.

### 2. Canonical Schema Authority Replaces Emergent Schema Drift
`DOM-CORE-002` establishes a canonical runtime schema and treats deviations as non-compliant rather than normal migration churn. This is a direct answer to prior periods where schema intent had to be inferred from iterative migration repairs.

### 3. FEAT as the Only Legal Mutation Orchestrator
`FEAT-CORE-000` requires context-first, idempotent, audited, single-transaction execution for all state mutation and cross-domain coordination. This responds to historical pressure around partial writes, retry behavior, and distributed side effects.

### 4. Invariants Move from Implied Practice to Enforced Constraint
`INV-CORE-000` and `INV-ARC-000` convert tenancy, capability evaluation, command boundaries, and observability into architectural constraints. The migration history repeatedly shows these concerns being corrected reactively; V2 makes them proactive and enforceable.

### 5. Scope Model Consolidation
The restructuring corpus converges scope and identity around explicit class/seat authority while retaining join-code semantics as controlled boundary metadata. This aligns with the observed trajectory from teacher/block-era patching toward stronger class-scoped normalization.

---

## Connection: Historical Migration to V2 Decisions
The migration archive and V2 doctrine describe the same system at different layers:

- Migrations show what had to be repaired, merged, and normalized over time.
- V2 documents codify the constraints intended to prevent recurrence of those same failure modes.

This is not a simple “lessons learned” appendix. It is a continuity statement:
- Historical migrations reveal recurring architectural stress points.
- V2 turns those stress points into design-time constitutional rules.

Practically, that means V2 is best understood as a governance and execution model built from observed schema history, not an abstract redesign detached from implementation reality.

---

## Current Historical Position
By the observed head migration (`f9a8b7c6d5e4`, Apr 20, 2026), the project had already entered a policy-driven and correlation-aware operating model. V2 documentation formalizes this direction by defining:
- who owns mutation authority,
- where runtime truth resides,
- how execution must occur,
- and which invariants cannot be violated by future development.

