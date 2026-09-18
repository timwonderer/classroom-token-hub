# FEAT-CLASS-006: Destroying a Class Boundary

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---| --- | --- | --- |
| FEAT-CLASS-006 | 1.0 | 2026-09-17 | N/A (extracted from FEAT-CLASS-001) | Normative |

---

## I. Purpose

This FEAT defines the canonical workflow for destroying an existing Class
Boundary while its owning principal survives.

Destroying a Class Boundary removes:

- the Class;
- every record scoped to that `class_id`;
- every Seat in that class, including the administrative Teacher Seat;
- the class's configuration, engine, and policy lineage.

It is the counterpart of `FEAT-CLASS-001`, not a mode of it. `FEAT-CLASS-001`
establishes a boundary and guarantees that exactly one is established; this
workflow guarantees that one ceases to exist. They share a domain and nothing
else: different context requirements, different authority, opposite terminal
state, and — because destruction removes otherwise immutable economic history —
different constitutional standing.

This FEAT owns orchestration only. Persistence remains delegated to the owning
domains.

### Why this is a separate execution identity

Each request executes a single command path whose domain, capability, and action
are recorded as part of its observability (`INV-ARC-000` §VIII.2). A FEAT names a
user-facing action and orchestrates the domain contracts that action requires
(`INV-CORE-001`); it is not a bucket for operations that happen to touch the same
table. Recording the destruction of a class universe under a FEAT whose contract
guarantees creation makes the audit statement false, not merely untidy.

Destruction also carries its own constitutional semantics. `class_id` is the
existential root of class-scoped state: scoped data must not survive deletion of
its `class_id` unless explicitly re-scoped (`INV-CORE-000` §26, §33), and a
principal left holding no Seat anywhere cannot exist (`DOM-IDEN-005` §V.6, §VI).
Neither statement has any analogue in class creation.

---

## II. Constitutional Authority

### Primary Authority

**DOM-CLASS-001**

Authorizes destruction of a Class Boundary and of the class-scoped state rooted
at its `class_id`.

### Supporting Authority

**DOM-IDEN-005** — Seat destruction as a consequence of class teardown,
including the administrative Teacher Seat, and the principal-survival rule that
bounds this FEAT (§IV.2 below).

**INV-CORE-000 §III.5** — the terminal-destruction lifecycle exception, which is
the only basis on which otherwise immutable economic history may be removed. The
class-scope teardown sets `cth.class_universe_destroying` for exactly that
reason.

---

## III. Execution Context

This workflow SHALL execute within a CanonicalContext for the class being
destroyed.

Required:

- authenticated `user_id`
- `class_id` of an existing, teacher-owned Class Boundary
- `actor_role = teacher`

This is the inverse of `FEAT-CLASS-001` §III, which SHALL NOT execute within
CanonicalContext because its target does not yet exist. Here the target must
already exist, and a context is what identifies it.

### Authority resolution

The class destroyed is the one named by the canonical context. No display name,
`join_code`, public identifier, or other form-supplied value participates in
resolving the destruction target (`INV-CORE-000` §III.4). Display values reaching
this surface exist only to render the human-readable confirmation phrase; they
never select, switch, or authorize a target.

---

## IV. Workflow

1. Acquire the destruction locks: the owning principal's `users` row, then the
   `classes` row, in that order.
2. Re-evaluate the authoritative state under those locks (§IV.2).
3. Destroy the class-scoped records and the class's Seats.
4. Clear canonical pointers to the destroyed class on the surviving principal
   (`INV-ARC-012` §V).

### IV.1 Lock order

Both this FEAT and roster deletion serialize on the same two rows and SHALL take
them principal-first. A second order in either path would let them deadlock
against each other.

### IV.2 Locked re-evaluation and fail-closed boundary

Dispatch to this FEAT happens **before** it opens, from a read that holds no
lock. That read selects the executor; it never authorizes the destruction.

This FEAT SHALL therefore re-evaluate, inside its own transaction and under the
locks of §IV.1, whether class destruction is still the lawful result — that is,
whether the class still holds a Seat of its owning principal in some other
class, so that the principal survives this teardown.

If it no longer does, the principal's last Seat is inside the target class, and
destroying it would leave a principal holding no Seat anywhere — which
`DOM-IDEN-005` §V.6 and §VI forbid, granting teachers no exception. That command
is `FEAT-IDEN-007`, not this one. This FEAT SHALL then **fail closed with no
mutation**: it destroys nothing, and the caller re-confirms against the real
consequence, whose confirmation phrase is the stronger one.

A narrower FEAT SHALL NOT perform a wider destruction than its own contract
covers, regardless of what the dispatching read observed.

---

## V. Composition

One FEAT executes per request (`INV-ARC-000` §VIII.2, `INV-ARC-021` §V.2). This
FEAT composes **domain commands**, never other FEATs: class teardown calls the
plain `_destroy_class_scope_rows` command.

A caller that already holds a FEAT context SHALL invoke that domain command
directly rather than this envelope. `FEAT-IDEN-007` does exactly that when it
tears down each class owned by a principal it is destroying.

### Entry points

| Surface | Condition | FEAT |
|---|---|---|
| `POST /admin/join-code/delete` | class destroyed, principal survives | **FEAT-CLASS-006** |
| `POST /admin/join-code/delete` | class holds the principal's last Seat | `FEAT-IDEN-007` |
| Roster deletion emptying the final roster, principal survives | class destroyed | **FEAT-CLASS-006** |
| Roster deletion emptying the final roster of the final class | principal destroyed | `FEAT-IDEN-007` |
| Roster deletion leaving the class standing | Seats removed | `FEAT-IDEN-006` |

---

## VI. Boundary

Routes own the destruction gate (30-second countdown, exact typed phrase,
10-second press-and-hold) and the confirmation presentation. They SHALL NOT
delete class or identity rows inline.

This workflow SHALL NOT destroy the owning principal, any Seat outside the
target class, or any other class owned by the same principal. Sibling classes
survive.

Post-destruction session teardown and the clearing of canonical pointers are
route concerns for the surviving actor.

---

## VII. Failure

Destruction SHALL execute atomically. The workflow SHALL either complete
successfully or roll back completely. No partially destroyed Class Boundary
SHALL persist — a failure anywhere in the teardown leaves the class intact
rather than stripped of some of its records.

A refusal under §IV.2 is not a failure of this kind: nothing was attempted, and
no rollback is required to leave the class whole.

---

## VIII. Guarantees

This FEAT guarantees:

- exactly one Class Boundary ceases to exist;
- no record scoped to that `class_id` survives it unless explicitly re-scoped
  (`INV-CORE-000` §26, §33);
- every Seat in that class is destroyed, the administrative Teacher Seat
  included;
- the owning principal survives, still seated in at least one other class;
- sibling classes and their records are untouched;
- destruction that would orphan the principal does not occur under this FEAT.

---

## IX. Delegation

This FEAT delegates to:

- DOM-CLASS-001
- DOM-IDEN-005
- FEAT-CORE-000

---

## X. Provenance

Class destruction previously executed under `FEAT-CLASS-001`, designated by
`FEAT-IDEN-007` §Composition while `FEAT-CLASS-001`'s own contract described only
creation and its §III forbade executing within a CanonicalContext. The two
Normative documents therefore disagreed about what `FEAT-CLASS-001` was. That
designation is normative debt, not precedent: `FEAT-CLASS-001` is
class-boundary creation only, and every reference designating it for destruction
has been retargeted here.
