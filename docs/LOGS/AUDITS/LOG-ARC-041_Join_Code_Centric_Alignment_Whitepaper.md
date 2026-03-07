# LOG-ARC-041: Join-Code-Centric Alignment Whitepaper

**Date:** 2026-03-07  
**Primary Branch Reviewed:** `codex/fix-database-model-for-dob-sum-storage`  
**Baseline / Related Branch:** `join-code-centric-architecture-rebuild`  
**Merge Base:** `69e5a493`

## Executive Summary

This branch continues the same architectural direction established in `join-code-centric-architecture-rebuild`: join code is the tenancy boundary, and seat-scoped identity is the unit of authorization and auditability. The practical goal is to eliminate residual cross-class leakage vectors, remove legacy identity shortcuts, and make sensitive data handling safer by default.

From the commit history, the branch contributes three concrete outcomes:

1. Completes additional join-code scoping hardening in admin/API/student execution paths (especially tap/hall-pass/rent flows).
2. Advances the identity model from legacy/demo assumptions toward `users` + `seats` + membership-driven context.
3. Reduces privacy risk by replacing plaintext DOB-derived storage with HMAC-based persistence and tightening PII handling.

In short: `join-code-centric-architecture-rebuild` established the architectural contract; this branch operationalizes that contract deeper in runtime behavior and data storage.

## What This Branch Is Trying To Accomplish

### 1) Close Remaining Context-Leak Paths in Day-to-Day Flows

The latest commits are concentrated around tenant isolation in paths with high mutation and high frequency:

- `c4590185` seat-scoped rent lookups in admin flows
- `ddcc0e36` admin hall-pass and rent class scoping tightened
- `685736bf` admin/API join-code scoping hardening for taps/history
- `8fa7df4a` enforced student class context and block scope in API
- `2a939e01`, `9a689b36`, `a5c79236`, `1ec658d9` further hardening of tap mutations, tap-in locking, daily limits, and student tap setting reads

These changes indicate a deliberate move from partial scoping to comprehensive scoping: read paths, write paths, and limit enforcement now consistently anchor to class context instead of legacy/global assumptions.

### 2) Finish the Identity Migration Pattern

Several commits show the branch carrying the architecture from conceptual model into concrete runtime dependencies:

- `5444d538` remove demo sessions; introduce `users`/`seats` with seat-scoped ledger + attendance
- `40d94533` continue seat-scoped identity migration

This is not cosmetic refactoring. It reduces ambiguity in "who acted, in which class context" and supports stronger audit traces across transaction-like events.

### 3) Enforce Least-PII Data Practices

Security and privacy hardening appears as a first-class objective, not an afterthought:

- `1468d549` replace plaintext `TeacherBlock.dob_sum` with HMAC hash
- `f8efb1f2` harden PII persistence and remove archive columns

Combined with tenancy scoping, this lowers both exposure radius (which class can access what) and data sensitivity at rest (what is stored in reversible/plain form).

## How This Fits `join-code-centric-architecture-rebuild`

The related branch delivered the foundational architecture: `ClassEconomy`/`ClassMembership`, query inversion toward join-code-first reads, DB-level constraints, actor audit anchors, and teacher-shadow identity refactor (`3d7186d6`, `1e4953ef`, `c3e785fc`, `830bc6ec`, `a8b5dccf`, `8fcc5262`).

This branch aligns by extending those same principles to the operational edges where regressions usually reappear:

1. **From model-level correctness to route-level consistency**  
   `join-code-centric-architecture-rebuild` made the schema and core queries tenancy-aware; this branch applies that discipline in specific admin/student/API interaction paths.

2. **From identity abstractions to enforced seat context**  
   The rebuild branch introduced the new identity architecture; this branch uses it to replace remaining legacy/demo shortcuts in production paths.

3. **From audit anchors to safer persisted artifacts**  
   The rebuild branch added actor linkage and constraints; this branch further improves forensic and compliance posture by minimizing plaintext PII.

## Strategic Interpretation

Viewed together, both branches represent a two-phase architecture execution pattern:

1. **Phase A (Rebuild branch):** establish the contract (join-code tenancy, membership authorization, actor anchoring, query inversion).
2. **Phase B (Current branch):** reduce implementation drift by hardening high-risk flows and finishing identity/PII migrations.

That sequencing is sound. Architecture rebuilds fail when invariants stay abstract; this branch turns the invariants into difficult-to-bypass runtime behavior.

## Recommended Next Focus

To complete the trajectory implied by both histories:

1. Add/expand regression suites specifically for cross-join-code mutation attempts in tap, hall-pass, rent, and attendance paths.
2. Track a "legacy-lookup burn-down" metric (remaining `teacher_id`-anchored logic paths and fallback behaviors).
3. Validate migration completeness for seat-scoped identity in reporting, exports, and diagnostics endpoints that are less frequently exercised.

The commit record supports a clear conclusion: this work is not a side quest to the rebuild. It is the consolidation layer that makes the join-code-centric architecture durable under real operational pressure.
