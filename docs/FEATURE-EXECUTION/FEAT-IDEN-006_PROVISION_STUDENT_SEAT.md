# FEAT-IDEN-006 — Provision Student Seat in Existing Class

## Contract

Student roster upload/paste-grid provisioning is an IDENTITY operation. It
creates an unclaimed student `Seat` and its `IdentityProfile` inside an
already-created class. Class creation is a separate CLASS operation.

The FEAT requires canonical teacher context scoped to the existing class and
explicit `correlation_id` and `idempotency_key` metadata. It validates teacher
ownership and class scope before the atomic seat/profile mutation.

## Boundary

Routes may collect roster input and resolve the existing `class_id`, but they
must not create seats or profiles inline. `FEAT-CLASS-002` owns class-boundary
modification; `FEAT-IDEN-006` owns identity seat provisioning.

Authority: DOM-IDEN-007, DOM-CLASS-001, SOP-DEV-002.


## Additive roster import (2026-09-15)

Each accepted upload row provisions a NEW unclaimed Seat and IdentityProfile.
Do not match, skip, update, or deduplicate against existing seats by name,
regardless of claim status. In particular, names matching a claimed student are
new provisioning requests. Duplicate-name resolution applies only within the
submitted batch: reject the batch until the teacher distinguishes the names or
supplies distinct claim deduplication codes. Validate the whole batch before
writing; all accepted rows commit in one FEAT transaction. This additive import
is distinct from actor_public_id-based modification of an exported roster under
FEAT-CLASS-002. Notes are passed to the encrypted profile field.
