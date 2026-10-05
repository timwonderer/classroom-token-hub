"""Which Support tickets system support may see or act on (DOM-SUP-001 §VIII).

`support_disclosure` decides which fields of a ticket reach an operator. This
module decides which tickets reach one at all, and it is the only place that
does: every sysadmin list, count, detail and mutation starts from
`sysadmin_visible_issues()`.

A ticket is visible to system support when either

- a teacher escalated it (`escalated_at` is set), or
- a teacher wrote it: its `actor_public_id` is a teacher seat in the ticket's
  own class. That is the direct teacher report of DOM-SUP-001 §X, which is
  addressed to system support from the moment it is submitted.

A student ticket is the teacher's to review. Before the teacher escalates it,
system support has no read of it and no transition on it (DOM-SUP-001 §VIII:
`OPEN`, `TEACHER_REVIEW` and teacher closure are teacher or system acts;
FEAT-SUP-001: student input cannot grant system-support access). A student
ticket the teacher closes without escalating never becomes visible.

Why these two signals:

- `escalated_at` is written only by the teacher escalation FEAT, atomically
  with `ESCALATED_TO_DEV` and its history row, and nothing clears it. Status
  is not a substitute: a ticket keeps being "escalated" after it moves on to
  `DEV_RESOLVED`, `TEACHER_FINAL_REVIEW` or `CLOSED`, and a teacher can move a
  never-escalated ticket to `TEACHER_FINAL_REVIEW` directly.
- Authorship is read from Identity (`seats.role`), which DOM-SUP-001 §VII lets
  Support read for context. `create_support_ticket` accepts only a teacher
  seat in the ticket's class, and student submission only a student seat. The
  correlation pack's `actor_type` records the same fact, but it is audit
  evidence and deliberately not consulted: the existence or content of
  correlation data grants no ticket access (DOM-SUP-001 §VI).

Everything else fails closed: a ticket matching neither signal is treated
exactly like one that does not exist.
"""
from __future__ import annotations

from sqlalchemy import and_, exists, or_

from app.models import ClassEconomy, Issue, Seat


def teacher_authored_clause():
    """SQL predicate: the ticket was submitted by a teacher seat of its own class."""
    return exists().where(and_(
        Seat.public_id == Issue.actor_public_id,
        Seat.role == 'teacher',
        Seat.class_id == ClassEconomy.class_id,
        ClassEconomy.class_public_id == Issue.class_public_id,
    )).correlate(Issue)


def student_authored_clause():
    """SQL predicate: the ticket is not a teacher's direct report.

    The teacher's review queue and its review/resolve/escalate/close actions
    work on these only. A teacher's own ticket is addressed to system support
    (DOM-SUP-001 §X); it has no teacher-review stage, so it must never surface
    as something the teacher reviews.
    """
    return ~teacher_authored_clause()


def escalated_clause():
    """SQL predicate: a teacher escalated the ticket to system support."""
    return Issue.escalated_at.isnot(None)


def sysadmin_visible_clause():
    """SQL predicate: system support may see or act on this ticket."""
    return or_(escalated_clause(), teacher_authored_clause())


def sysadmin_visible_issues():
    """Base query for every sysadmin projection of `issues`."""
    return Issue.query.filter(sysadmin_visible_clause())


def get_sysadmin_visible_issue(issue_id):
    """The ticket if system support may see it, else None (callers 404 either way)."""
    if issue_id is None:
        return None
    return sysadmin_visible_issues().filter(Issue.id == issue_id).first()


def sysadmin_direct_lifecycle_issues():
    """Visible tickets on the direct (teacher report, never escalated) lifecycle.

    Only these may be moved by the sysadmin ticket-update form. An escalated
    ticket moves through the escalation workflow instead, where system
    support's only transition is `ESCALATED_TO_DEV` -> `DEV_RESOLVED`.
    """
    return sysadmin_visible_issues().filter(
        teacher_authored_clause(),
        ~escalated_clause(),
    )


def is_sysadmin_direct_lifecycle(issue_id):
    return sysadmin_direct_lifecycle_issues().filter(Issue.id == issue_id).first() is not None
