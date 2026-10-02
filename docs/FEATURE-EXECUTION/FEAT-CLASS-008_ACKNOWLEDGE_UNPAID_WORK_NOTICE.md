# FEAT-CLASS-008: Acknowledge the Unpaid-Work Notice

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-CLASS-008 | 1.0 | 2026-10-01 | N/A (new; owner rulings 2026-10-01) | Normative |

---

## I. Purpose

This FEAT records that a class's teacher dismissed the notice for work recorded
before the class's first payroll setting (`DOM-PROD-001` §XV.6).

The notice is a one-time bootstrap guard. Dismissing it records one fact, that
the teacher saw it. It does not change payroll, attendance or any other domain's
state, and it does not assert that the notice's condition still holds.

*Numbering.* `FEAT-CLASS-007` is not used here. The FEAT registry reconciliation
of 2026-09-19 (`docs/TRACKING/`) proposes that id for the successor of
`FEAT-SETTINGS-001`, and one id must name one workflow.

---

## II. Constitutional Authority

### Primary Authority

**DOM-CLASS-001** §VII.1 — `classes.unpaid_work_notice_acknowledged_at` is a
class-level operating fact owned by Class Configuration and written only by this
FEAT.

### Supporting Authority

- **DOM-PROD-001** §XV.6 — owns the notice's condition and its meaning. This FEAT
  never evaluates that condition.
- **INV-ARC-019** — the acting principal is the class's teacher seat, never a
  `users.id` stored on the class.
- **INV-ARC-007** — the notice is shown on GET; acknowledging is a separate POST.
  Rendering never acknowledges.
- **INV-ARC-013** — the value lives on the class row and is destroyed with it.

---

## III. Execution Context

Requires a `CanonicalContext` with `user_id`, `class_id`, `seat_id` and
`actor_role = teacher`. The surface is an explicit, CSRF-protected POST from the
teacher's dashboard or payroll page. Students and system administrators have no
surface for it.

### Authority resolution

All of the following must hold, or the FEAT fails closed and writes nothing:

1. the target `class_id` equals the context's `class_id`. A form that names a
   different class is refused rather than redirected to the active one;
2. the actor owns the class (`verify_teacher_owns_class(class_id, user_id)`);
3. the acting seat is that class's teacher seat: `seat_id` belongs to `class_id`,
   has role `teacher`, and is bound to the acting user.

A class has exactly one teacher seat, so who acknowledged is derivable from the
class and is not stored.

---

## IV. Workflow

1. Resolve authority (§III).
2. Resolve the current instant through the canonical temporal resolver.
3. Issue one conditional update:
   `UPDATE classes SET unpaid_work_notice_acknowledged_at = :now
   WHERE class_id = :class_id AND unpaid_work_notice_acknowledged_at IS NULL`.
4. Return the stored timestamp and whether this call recorded it.

The FEAT does not read `payroll_settings` or `attendance_sessions` and does not
refuse when the notice's condition no longer holds (`DOM-PROD-001` §XV.6).

---

## V. Guarantees

- **Write-once.** The timestamp is set at most once and is never cleared or
  overwritten.
- **Idempotent.** A second dismissal, a replay, or two concurrent dismissals all
  succeed. Exactly one writes; the stored value is the first one.
- **Stale dismissals are harmless.** A dismissal submitted after the class's first
  payroll setting exists is recorded like any other.
- **Class-scoped.** Acknowledging one class never affects another class, including
  another class of the same teacher.
- **No side effects elsewhere.** No productivity, payroll, ledger or policy row is
  written or read for authority.

---

## VI. Failure

| Condition | Result |
|---|---|
| Missing or non-teacher context | Refused, nothing written |
| Target class differs from the context class | Refused, nothing written |
| Actor does not own the class | Refused, nothing written |
| Acting seat is not the class's teacher seat | Refused, nothing written |
| Already acknowledged | Success, nothing written, first timestamp returned |

---

## VII. Provenance

Owner rulings 2026-10-01 on the unpaid-work alert: one-time bootstrap guard;
acknowledgement independent of resolution; stored on `classes` as
`unpaid_work_notice_acknowledged_at`; teacher only; attributed to the class's
teacher seat by derivation.
