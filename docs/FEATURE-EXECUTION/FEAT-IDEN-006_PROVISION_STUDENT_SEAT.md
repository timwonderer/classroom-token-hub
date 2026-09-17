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
Do not match, skip, or merge rows into existing seats by name, regardless of
claim status. In particular, names matching a claimed student are new
provisioning requests. Every unclaimed Seat sharing a claim name must remain
independently claimable: under the class lock, the system (never the teacher)
assigns distinct claim deduplication codes to each new row in such a group and
to any existing unclaimed namesake that lacks a unique code. Import changes no
field of an existing Seat other than that code and its derived roster fingerprint. Validate the whole batch before writing; all
accepted rows and code assignments commit in one FEAT transaction. This additive import
is distinct from actor_public_id-based modification of an exported roster under
FEAT-CLASS-002. Notes are passed to the encrypted profile field.


## Roster removal and terminal consequences (2026-09-15)

Teacher-authorized deletion uses the active canonical class and explicit student
Seat IDs; cross-class, teacher-seat, missing, or malformed selections fail closed.
One transaction locks the teacher and class, verifies the current roster, and
composes Identity removal or class/account destruction as appropriate. The
confirmation phrase must match the current consequence, including deletion of
the class and teacher account when their final student/class is removed.
Delete physically destroys the Seat; it is not an implicit Unclaim operation.

## Explicit Unclaim (2026-09-15)

Under INV-ARC-019 and DOM-IDEN-005, a teacher may explicitly Unclaim one claimed
student Seat in the active owned class. This is separate from Delete. Require
fresh first/last claim names, explicit confirmation, and the Seat's displayed
claim generation. Reject malformed input, stale generation, already-unclaimed
Seats, teacher Seats, and foreign-class Seats without mutation. Duplicate unclaimed
names must remain independently claimable using distinct nonempty codes; otherwise
reject the change and ask the teacher to distinguish the names/codes.

One FEAT transaction validates/locks teacher ownership, class, detached principal,
and Seat; writes only Identity state; clears the binding and claimed_at; increments
claim_generation; preserves profile names and notes; uses the entered names only to regenerate
normal seat claim hashes/fingerprint/code; and clears that principal's active context
when it points at the detached Seat. Revoke this Seat’s outstanding teacher-recovery code without rerolling recipients;
preserve accepted class confirmation and any remaining selected recipient.
Delete the old User only if no surviving Seat/class ownership remains. Preserve
Seat/public_id/class_id, profile, balances, transactions, attendance, items, support
records, and other Seat-owned facts. Unclaim does not invoke last-student deletion.

Initial claim verification must capture the server-stored claim_generation in the
signed onboarding session. Credential completion rechecks it under the class/Seat
lock; missing/stale generations fail closed. Authenticated binding revalidates the
live principal and claim material under the same class lock. A new claimant uses
the ordinary claim flow; an existing account uses authenticated class binding.
