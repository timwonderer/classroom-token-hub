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


## Roster removal and terminal consequences (2026-09-15, amended 2026-09-17)

Teacher-authorized deletion uses the active canonical class and explicit student
Seat IDs; cross-class, teacher-seat, missing, or malformed selections fail closed.
One transaction locks the teacher and class and verifies the current roster. The
confirmation phrase must match the current consequence, including deletion of
the class and teacher account when their final student/class is removed.
Delete physically destroys the Seat; it is not an implicit Unclaim operation.

**This FEAT owns roster removal only** — the case in which the seats go and the
class universe survives. It does not own the terminal consequences. Emptying the
final roster destroys the class universe, which `FEAT-CLASS-006` owns; doing so
to the principal's final class destroys the principal, which `FEAT-IDEN-007`
owns. The route dispatches to the owning FEAT before that FEAT opens, so exactly
one FEAT executes per request (INV-ARC-000 §VIII.2) and the FEAT recorded in
`feat_code` is the one whose contract covers what was destroyed.

The dispatching preview holds no lock and authorizes nothing; it selects the
FEAT. The selected executor takes the teacher and class locks, re-derives the
plan, and **fails closed** if the terminal scope has changed since the preview
(DOM-CLASS-001 §Terminal Roster Deletion). A narrower FEAT must never perform a
wider destruction than its contract covers.

Amended 2026-09-17. The previous wording had this FEAT "compose Identity removal
or class/account destruction as appropriate", which attributed class-universe and
principal destruction to a MED-blast-radius provisioning FEAT and left the HIGH
idempotency discipline of `FEAT-IDEN-007` and `FEAT-CLASS-006` inapplicable to
the most destructive operation in the system. The three consequences are mutually
exclusive, so routing by scope still yields one envelope per request and keeps
destruction atomic.

## Explicit Unclaim (2026-09-15)

Under INV-ARC-019 and DOM-IDEN-005, a teacher may explicitly Unclaim one claimed
student Seat in the active owned class. This is separate from Delete. Require
fresh first/last claim names, explicit confirmation, and the Seat's displayed
claim generation. Reject malformed input, stale generation, already-unclaimed
Seats, teacher Seats, and foreign-class Seats without mutation. Duplicate unclaimed
names must remain independently claimable: under the class lock, the system (never
the teacher) assigns distinct claim deduplication codes to the unclaimed Seat and any
unclaimed namesake lacking a unique code, exactly as additive import does.

One FEAT transaction validates/locks teacher ownership, class, detached principal,
and Seat; writes only Identity state; clears the binding and claimed_at; increments
claim_generation; preserves profile names and notes; uses the entered names only to regenerate
normal seat claim hashes/fingerprint, with any code system-assigned; and clears that principal's active context
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
