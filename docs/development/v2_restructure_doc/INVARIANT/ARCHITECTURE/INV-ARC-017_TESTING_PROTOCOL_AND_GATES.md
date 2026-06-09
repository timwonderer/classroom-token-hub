# INV-ARC-017: Testing Protocol and Gates

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-017      | 1.1     | 2026-06-08     | V2-TEST-000 v1.0 | Constitutional |

## I. Purpose

This document defines the canonical testing protocol for the `codex/v2.0` rebuild. It standardizes when tests must run, what must be tested, the scope of each test set, how to execute each set, how to report results, and which test sets are required for common repository events.

## II. Scope

This protocol applies to all repository changes that can affect runtime behavior, migration behavior, documentation claims about runtime behavior, or release readiness.

It governs:

- local development validation
- feature and bug-fix verification
- migration and schema validation
- cross-domain and regression validation
- tracker and documentation claims about test status
- release and deployment readiness checks

It does not replace task-specific instructions in a more specific constitutional, domain, FEAT, SOP, or tracker document. Where another active document imposes a stricter gate, the stricter gate applies.

## III. Authority Level

Constitutional. This protocol derives from `INV-CORE-000` and `INV-CORE-001` and is intended to standardize testing behavior across the repository. It is subordinate to foundational invariants and may not weaken them.

## IV. Dependencies

- `docs/development/v2_restructure_doc/SOP-DOC-000_DOCUMENTATION_STANDARD.md`
- `docs/development/tracking/V2_Full_compliance_migration_plan.md`
- `docs/development/tracking/V2_REBUILD_VALIDATION_REPORT.md`
- `docs/development/v2_restructure_doc/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/development/v2_restructure_doc/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/development/v2_restructure_doc/INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md`
- `docs/development/v2_restructure_doc/INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `docs/development/v2_restructure_doc/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`

## V. Testing Principles

1. Testing must be proportional to the change.
2. Tests must prove the changed behavior and the most likely adjacent regressions.
3. Tests must be scoped to the affected contract, domain, or subsystem before broader suites are considered.
4. The full suite must not be treated as the default action for every change.
5. A test result may only be reported as passing when the exact command and scope are recorded.
6. A claim of coverage must be tied to concrete execution evidence, not inference.

## VI. When Testing Is Required

Testing is required before any claim of completion, merge readiness, release readiness, or tracker advancement.

Tests must be run when any of the following occur:

1. Application code changes.
2. Migration changes.
3. FEAT changes.
4. Service changes.
5. Route changes.
6. Model changes.
7. Authentication, tenancy, authority, or invariant changes.
8. Bug fixes.
9. Documentation changes that assert runtime behavior, migration state, or validation status.
10. Any change that can affect existing test assumptions.

The full suite is required only when:

- a release gate explicitly demands it
- a large cross-cutting refactor touches multiple domains
- a prior regression cannot be isolated with smaller sets
- a tracker, release, or operator decision depends on whole-repo confidence

## VII. What Must Be Tested

At minimum, every change set must test the following categories as applicable:

1. Changed path success behavior.
2. Changed path failure and denial behavior.
3. Relevant authorization and scoping behavior.
4. Relevant migration upgrade and downgrade behavior.
5. Relevant invariant behavior.
6. Adjacent regression surfaces.
7. Any contract explicitly mentioned in tracker, spec, or issue text.

When a change touches one of the following, the corresponding category must be included:

- `class_id` or `join_code` logic: cross-class scoping, fail-closed lookup, and public/private boundary behavior
- FEAT code: mutation ownership, idempotency, and commit behavior
- GET handlers: no-write behavior and side-effect suppression
- migrations: upgrade, downgrade, re-upgrade, and head validation
- time-sensitive logic: class-local temporal boundaries and UTC storage behavior
- documentation claims: supporting runtime or test evidence must exist

## VIII. Test Scope Sets

The repository standardizes the following test sets. These are the canonical units of execution.

### A. Micro Set

Purpose:

- validate a small helper, single function, or isolated guard

Typical scope:

- one test file
- one test function
- one narrow `-k` expression

Use when:

- the change is localized
- the surface area is trivial
- the goal is immediate feedback

### B. Slice Set

Purpose:

- validate the changed feature slice and its nearest regressions

Typical scope:

- 2 to 6 related test files
- one domain or one feature workflow

Use when:

- a route, FEAT, service, or model change spans more than one file
- the change affects a single user journey or invariant boundary

### C. Domain Set

Purpose:

- validate an entire domain contract

Typical scope:

- all tests directly tied to one domain
- adjacent tenancy or invariant tests

Use when:

- the change affects a domain boundary
- a schema or FEAT change crosses multiple routes or services within one domain

### D. Gate Set

Purpose:

- validate the repository-level checkpoint for a significant milestone

Typical scope:

- the full domain set for the affected area
- adjacent cross-domain regression suites
- migration or invariant checks

Use when:

- landing a wave
- merging a cross-cutting refactor
- validating a migration chain

### E. Full Suite

Purpose:

- validate whole-repo readiness

Typical scope:

- `pytest` without narrowing

Use when:

- the release or tracker explicitly requires whole-repo confidence
- the change is large enough that targeted scope would be misleading
- a prior gate failed in a way that could have hidden broader regressions

## IX. Canonical Test Sets by Event

The following sets are required by default unless the change is narrower and a smaller set clearly proves the contract.

### 1. Small Code Fix

Required:

- Micro Set for the changed function or file
- one adjacent regression test if the bug affected behavior beyond the function itself

Optional:

- Slice Set if the bug involved a route, FEAT, or domain boundary

### 2. Route Change

Required:

- Slice Set for the route file
- authorization or scoping tests for affected class/seat/user boundaries
- any GET-write or CSRF checks that apply

### 3. FEAT Change

Required:

- Slice Set for the FEAT file
- mutation ownership validation
- idempotency validation
- any touched route or service tests

### 4. Service Change

Required:

- Slice Set for the service file
- domain-contract tests
- adjacent boundary or invariant tests

### 5. Model Change

Required:

- model-specific tests
- migration validation if schema changed
- related service or FEAT tests that exercise the model

### 6. Migration Change

Required:

- migration lint, when available
- upgrade test
- downgrade test
- re-upgrade test
- head verification

### 7. Tenancy or Authority Change

Required:

- class-scoped tests
- cross-class rejection tests
- fail-closed lookup tests
- any affected auth/session tests

### 8. Temporal or Scheduled Behavior Change

Required:

- class-local time tests
- deterministic boundary tests
- scheduler or idempotency tests if applicable

### 9. Documentation-Only Change

Required:

- no runtime test execution is required unless the doc changes a runtime claim, a tracker claim, or a protocol claim
- if the doc asserts runtime behavior, the supporting runtime tests must already exist or be rerun before the claim is made

### 10. Wave or Release Validation

Required:

- the wave-specific gate set defined in the tracker
- any migration gate
- any invariant gate explicitly referenced by the wave
- full suite only if the tracker says so or if the wave is broad enough to justify it

## X. Execution Procedure

Testing must be executed in the following order unless a narrower sequence is explicitly sufficient:

1. Identify the contract changed.
2. Select the smallest test set that proves the contract.
3. Run the smallest set first.
4. Expand to the next larger set only if the change crosses additional boundaries or if the first set exposes a regression.
5. Run migration or invariant gates before broader whole-repo checks when the change affects schema, FEAT ownership, or authority.
6. Escalate to the full suite only when a gate, milestone, or regression pattern requires it.

## XI. Running Tests

Test runs must be reproducible. Each report must include:

1. The exact command used.
2. The scope of the command.
3. The result summary.
4. Any failures, skips, deselections, or xfails relevant to the claim.
5. Whether the command is a micro, slice, domain, gate, or full-suite run.

Preferred execution patterns:

- single file: `pytest -q tests/test_example.py`
- explicit subset: `pytest -q tests/test_a.py tests/test_b.py`
- scoped expression: `pytest -q tests/test_domain.py -k "keyword"`
- migration gate: `flask db upgrade`, `flask db downgrade`, `flask db upgrade`
- syntax smoke: `python3 -m py_compile <files>`

When working on a wave, run the smallest proving set first, then the wave gate. Do not run the full suite unless the wave gate or evidence gap requires it.

## XII. Reporting Test Results

All test reporting must be concise, concrete, and evidence-based.

Required fields:

- command
- scope class
- result
- date or timestamp when relevant
- what changed since the last validated run

Permitted outcome labels:

- pass
- fail
- partial
- skipped
- blocked

Reporting rules:

1. Do not claim broader coverage than the command actually exercised.
2. Do not summarize a subset as "the suite" unless it was the suite.
3. If a run is partial, state what remains untested.
4. If a failure is environmental, state the environment condition and whether the test itself is still valid.
5. If a report updates a tracker or validation doc, the doc must reflect the exact scope of the run and not infer completion.

## XIII. Required Reporting Sets

The following reporting sets are canonical:

1. `micro` report
   - for helper-level changes
   - includes one command and one result

2. `slice` report
   - for route, FEAT, service, or model changes
   - includes all commands needed to prove the slice

3. `domain` report
   - for domain-wide changes
   - includes domain tests and adjacent invariants

4. `gate` report
   - for migrations, waves, and release readiness
   - includes the gate sequence and any whole-repo evidence required

5. `tracker` report
   - for changes that update validation or migration status
   - must cite the exact evidence that justifies the tracker edit

## XIV. Default Test Budgets

Unless a more specific document requires otherwise:

- micro changes should not start with the full suite
- route and FEAT changes should start with a slice set
- domain and migration changes should start with the domain or gate set
- full suite should be reserved for milestone validation, broad refactors, or unresolved regression risk

## XV. Amendment

Revisions to this document must increment the version number, update the effective date, preserve compatibility with `INV-CORE-000` and `INV-CORE-001`, and update any active tracker references that rely on this testing protocol.
