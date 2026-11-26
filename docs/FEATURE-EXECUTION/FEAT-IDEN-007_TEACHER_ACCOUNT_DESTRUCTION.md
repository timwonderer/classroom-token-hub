# FEAT-IDEN-007 — Teacher Account Destruction

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-IDEN-007 | 1.1 | 2026-11-23 | Prior unversioned contract | Normative |

## Contract

Terminal destruction of a teacher principal. The command destroys the `users`
row together with everything that principal owns: every class universe it holds
(`ClassEconomy` and all class-scoped records), the teacher-scoped settings,
activity, audit, rent, insurance, issue, store, and recovery/credential rows,
and any student seats left orphaned by those class teardowns.

Blast radius: **HIGH**. The operation is irreversible and removes otherwise
immutable economic history, which is lawful only under the terminal-destruction
lifecycle exception (INV-CORE-000 §III.5). The class-scope teardown sets
`cth.class_universe_destroying` for exactly that reason.

Manual destruction requires authenticated principal context, the existing explicit
destruction confirmation/step-up, and independent correlation/idempotency metadata.
The target is that authenticated principal alone; active classroom selection is not
required and must not be fabricated. The scheduled lifecycle entry derives a principal-only target
from the locked retention-policy check below; it does not fabricate a logged-in
teacher session.

## Authority resolution

Manual deletion authority comes from the authenticated principal context and explicit confirmation/step-up alone (INV-CORE-000 §III.4).
No display name, username, join code, public identifier, or any other
form-supplied value participates in resolving the destruction target. Display
values reaching this surface exist only to render the human-readable
confirmation phrase; they never select, switch, or authorize a target.

## Composition

One FEAT executes per request (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2). This FEAT
therefore composes **domain commands**, never other FEATs:

- per-class teardown calls the plain `_destroy_class_scope_rows` command, not the
  `FEAT-CLASS-006` envelope `_hard_delete_class_scope`;
- account-level teardown calls the `_delete_teacher_*` commands and
  `delete_admin_account_rows` directly.

One local envelope covers final principal/class destruction: a failure in local
teardown or mandatory audit rolls back that transaction rather than leaving partial
class destruction. Provider effects and the prior revocation of authentication are
separate durable steps; database rollback cannot reverse external deletion.

`FEAT-CLASS-006` is the entry point for destroying **one** class while the
owning account survives. The two entry points are not interchangeable; a caller
already holding a context must use the domain command.

This designation named `FEAT-CLASS-001` until 2026-09-17. That was wrong:
`FEAT-CLASS-001` is class-boundary **creation**, its §III forbids executing
within a CanonicalContext, and its §X guarantees only that a boundary is
established. Destruction now has its own contract, `FEAT-CLASS-006`.

`POST /admin/join-code/delete` therefore dispatches between them. A class
teardown destroys that class's seats, including the teacher's administrative
one, and a principal holding no seat anywhere cannot exist — DOM-IDEN-005 §V.6
and §VI, which grant teachers no exception. So when the target class holds the
acting principal's last seat, the request is not single-class destruction at
all: the route executes **this** FEAT instead, and the surviving-account
assurance on the confirmation surface must not be shown.

## Boundary

Routes own the destruction gate (30-second countdown, exact typed phrase,
10-second press-and-hold) and the confirmation presentation. They must not
delete identity or class rows inline. Post-destruction session teardown and the
clearing of canonical pointers (`User.last_active_class_id` /
`last_active_seat_id`, INV-ARC-012 §V) are route concerns for the surviving
actor; a destroyed principal has no pointers left to clear.

Authority: INV-CORE-000 §III.4, §III.5; INV-ARC-012 §V; INV-ARC-021 §V.2;
DOM-IDEN-001.


## Automatic and roster-terminal entry points (amended 2026-09-17)

Roster deletion that removes a principal's final student Seat in its final class
destroys the principal, so it is **this** FEAT, exactly as
`POST /admin/join-code/delete` is (see §Composition). The roster route dispatches
to it before any FEAT opens, and it composes the same plain account-destruction
domain command — never a nested FEAT. Roster deletion that empties a non-final
class is `FEAT-CLASS-006`; roster deletion that leaves the class standing is
`FEAT-IDEN-006`. The scheduled retention entry composes the same plain command
under this FEAT.

Because the dispatching preview holds no lock, the executor re-derives the
deletion plan under the teacher and class locks and fails closed if the terminal
scope has moved, so a narrower FEAT cannot destroy a principal
(DOM-CLASS-001 §Terminal Roster Deletion).

Manual routes retain their confirmation gate. Final-student deletion must warn
about class destruction and, when applicable, teacher-account destruction; it
must require the corresponding stronger confirmation before executing.

Amended 2026-09-17. This section previously read "composed by the final-student
roster deletion FEAT", which designated `FEAT-IDEN-006` — "Provision Student Seat
in Existing Class", blast radius MED — as the executing FEAT for principal
destruction. `feat_code` on audit rows and every FEAT-ENTRY record take their
value from the active FEAT, so the destruction was attributed to a provisioning
command. Nesting remains forbidden and atomicity is unchanged: the three roster
outcomes are mutually exclusive, so selecting the FEAT before it opens still
gives one envelope per request.

The scheduled entry locks/reloads the teacher User and requires either 180 days
since the last successful sign-in or 30 days since creation if never signed in.
Its authority derives directly from INV-CORE-000 §III.5 / DOM-IDEN-003, so it does
not require a browser confirmation or sysadmin approval. Recheck after acquiring
the same lock used by successful sign-in. One atomic account transaction performs
all owned-class teardown, orphan handling, and principal destruction.

## Credential-provider completion boundary

Follow DOM-IDEN-003 §VII.A and incorporated SPEC-IDEN-002. First commit revocation of
authentication authority, generation advance and supersession of credential operations.
Prevent new issuance. Outside any database transaction or row lock, attempt known remote
credential/user/alias deletion and principal reconciliation with an empty expected set.
Provider calls plus retry delays have a maximum total 15-second budget and at most three
attempts for transient failures; this is not a required wait. Do not blindly retry a
permanent rejection. Revalidate authority, operation stage and current local state in
a new transaction before final atomic destruction. Scheduled retention entry points
also recheck their governing policy at the applicable local boundary.

The committed destruction intent is itself the durable authority for completion. Final
revalidation checks that intent, the generation it recorded, that the principal still exists
and that no higher-precedence operation superseded it; it does not require the already revoked
session or credential authority. If the final local transaction fails, the intent remains
durable and the principal is not restored to authentication. A bounded retry in the same
request and then system reconciliation (FEAT-IDEN-108) resume only that recorded destruction,
never a new or wider one. The manual requester was authenticated and confirmed before intent was committed.

Bounded provider failure SHALL NOT block lawful local destruction. Delete all local
operation state with the principal, without tombstones or historical identity references.
System reconciliation later discovers residue from provider inventory. Local auth,
database and mandatory audit failures are not covered by the provider exception.

Use DOM-OPS-002 §2.5 outcome evidence without identity-derived fields. Report exactly
one truthful result: local destruction with verified cleanup; local destruction with
unverified external cleanup; or local destruction incomplete. Never infer provider
absence from a failed inventory. Late provider registration grants no local authority.

## Amendment

Increment version/date and reconcile DOM-IDEN-003/005, FEAT-IDEN-108 and SPEC-IDEN-002.
The 2026-11-23 amendment preserves atomic local destruction while separating provider
cleanup, approved bounded-failure handling and non-identifying outcome evidence.
