"""Terminal destruction of class universes and teacher accounts (FEAT-CLASS-006, FEAT-IDEN-007).

Domain commands composed by the FEAT envelopes in ``app/routes/admin.py`` and by
the teacher retention job in ``app/services/teacher_lifecycle.py``. They open no
FEAT of their own: the caller owns the transaction (INV-ARC-000 §VIII.2).
"""
from __future__ import annotations

import sqlalchemy as sa
from flask import current_app
from sqlalchemy import text

from app.extensions import db
from app.feats.base import InvariantViolation
from app.models import (
    Announcement, AttendanceSession, ClassEconomy, EntitlementEvent, HallPassLog,
    HallPassSettings, Issue, IssueResolutionAction, IssueStatusHistory, LedgerBalanceSnapshot,
    PayrollEvent, PayrollSettings, PendingAction, RentSettings, Seat, StoreItemVisibility,
    StoreProduct, Transaction, User,
)
from app.services.admin_identity_service import delete_admin_account_rows, delete_admin_credentials_for_user
from app.services.class_configuration_query_service import get_class_economy
from app.services.recovery_service import delete_recovery_rows_for_user
from app.utils.student_deletion import delete_orphaned_users


def _destroy_class_scope_rows(*, class_id, canonical_context, **_ignored):
    """Domain command: permanently remove records scoped to a destroyed class.

    Plain command — it opens no FEAT context of its own so that composing
    commands (teacher account destruction, which must destroy every owned class
    in one transaction) can call it inside their own envelope. FEAT contexts
    cannot nest: exactly one FEAT executes per request
    (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2 — compose domain commands, not FEATs).

    The boundary may enter through join_code, but internal deletion uses the
    canonical class_id anchor only.
    """
    if canonical_context is None or not getattr(canonical_context, "user_id", None):
        raise ValueError("canonical_context is required for class deletion")
    user_id = canonical_context.user_id

    if not class_id:
        current_app.logger.critical("P0 INVARIANT VIOLATION: class deletion invoked without class_id.")
        raise InvariantViolation("class deletion requires canonical class_id")

    # Append-only history is a within-universe invariant.  Explicit class-universe
    # destruction is the authorized lifecycle exception for immutable history rows.
    db.session.execute(text("SET LOCAL cth.class_universe_destroying = 'on'"))

    class_row = get_class_economy(class_id)
    if not class_row:
        return

    invalid_scope_rows = []
    scoped_models = (
        ("ledger_transaction", Transaction),
        ("attendance_sessions", AttendanceSession),
        ("hall_pass_logs", HallPassLog),
        ("payroll_event", PayrollEvent),
        ("student_items", EntitlementEvent),
        ("issues", Issue),
        ("announcements", Announcement),
    )
    for label, model in scoped_models:
        join_code_column = getattr(model, "join_code", None)
        class_id_column = getattr(model, "class_id", None)
        if join_code_column is None or class_id_column is None:
            continue
        count = db.session.query(model).filter(
            class_id_column.is_(None),
            ).count()
        if count:
            invalid_scope_rows.append(f"{label}={count}")
    if invalid_scope_rows:
        message = (
            f"class_id NULL rows detected for class_id={class_id}: {', '.join(invalid_scope_rows)}"
        )
        current_app.logger.critical("P0 INVARIANT VIOLATION: %s", message)
        raise InvariantViolation(message)

    scoped_student_ids = [
        sid for (sid,) in db.session.query(Seat.user_id)
        .filter(Seat.class_id == class_id, Seat.user_id.isnot(None))
        .distinct()
        .all()
    ]
    store_purchase_entitlement_ids_subq = (
        db.session.query(EntitlementEvent.entitlement_id)
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.acquisition_type == "PURCHASE",
        )
        .subquery()
    )
    tx_ids_subq = (
        db.session.query(Transaction.id)
        .filter(Transaction.class_id == class_id)
        .subquery()
    )
    _class_row = get_class_economy(class_id)
    _class_pub_id = _class_row.class_public_id if _class_row else None
    issue_ids_subq = (
        db.session.query(Issue.id)
        .filter(Issue.class_public_id == _class_pub_id)
        .subquery()
    )
    # Class-scoped records
    PendingAction.query.filter(
        PendingAction.class_id == class_id,
        PendingAction.entitlement_id.in_(sa.select(store_purchase_entitlement_ids_subq)),
    ).delete(synchronize_session=False)
    EntitlementEvent.query.filter(
        EntitlementEvent.class_id == class_id,
        EntitlementEvent.event_type.in_(["GRANTED", "CONSUMED", "EXPIRED", "REVOKED"]),
        EntitlementEvent.acquisition_type == "PURCHASE",
    ).delete(synchronize_session=False)
    AttendanceSession.query.filter(AttendanceSession.class_id == class_id).delete(synchronize_session=False)
    HallPassLog.query.filter(HallPassLog.class_id == class_id).delete(synchronize_session=False)
    PayrollEvent.query.filter(PayrollEvent.class_id == class_id).delete(synchronize_session=False)
    LedgerBalanceSnapshot.query.filter(LedgerBalanceSnapshot.class_id == class_id).delete(synchronize_session=False)
    Announcement.query.filter(
        Announcement.class_id == class_id,
    ).delete(synchronize_session=False)

    # Hold every seat in the class before its tickets are removed. Support keeps
    # no foreign key into `seats`, so a ticket inserted after this sweep would
    # outlive the class it belongs to (DOM-SUP-001 §X). Issue writers validate
    # the seat under FOR SHARE, which this conflicts with.
    from app.utils.student_deletion import lock_seats_for_deletion
    lock_seats_for_deletion(
        [row[0] for row in db.session.query(Seat.id).filter(Seat.class_id == class_id).all()]
    )

    # Issue data tied to this class
    IssueResolutionAction.query.filter(
        IssueResolutionAction.issue_id.in_(sa.select(issue_ids_subq))
    ).delete(synchronize_session=False)
    Issue.query.filter(Issue.class_public_id == _class_pub_id).delete(synchronize_session=False)

    # Financial ledger (only here)
    Transaction.query.filter(Transaction.class_id == class_id).delete(synchronize_session=False)
    PayrollSettings.query.filter(PayrollSettings.class_id == class_id).delete(synchronize_session=False)
    RentSettings.query.filter(RentSettings.class_id == class_id).delete(synchronize_session=False)

    # Remove store items and their visibility/entitlement rows for this class.
    # This is unconditional: destroying a class always tears down its store
    # catalog. (Previously gated on teacher block/section labels, which is
    # display-only metadata and never a valid precondition for cleanup.)
    # ``store_products.class_id`` is the isolation boundary, so every product
    # version in this class is deletable and no other class can reference one.
    # The previous version of this block asked the question sideways — it kept
    # any product that still had a visibility row, and it spared class-wide
    # products (which have no visibility rows at all) entirely.
    class_product_lineages = (
        db.session.query(StoreProduct.product_lineage_uuid)
        .filter(StoreProduct.class_id == class_id)
        .subquery()
    )
    StoreItemVisibility.query.filter(
        StoreItemVisibility.product_lineage_uuid.in_(sa.select(class_product_lineages))
    ).delete(synchronize_session=False)

    class_item_entitlement_ids = (
        db.session.query(EntitlementEvent.entitlement_id)
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.acquisition_type == "PURCHASE",
        )
        .subquery()
    )
    PendingAction.query.filter(
        PendingAction.class_id == class_id,
        PendingAction.entitlement_id.in_(sa.select(class_item_entitlement_ids))
    ).delete(synchronize_session=False)
    EntitlementEvent.query.filter(
        EntitlementEvent.class_id == class_id,
    ).delete(synchronize_session=False)
    StoreProduct.query.filter(
        StoreProduct.class_id == class_id
    ).delete(synchronize_session=False)

    # Seats/ownership for this class
    # One class cascade removes seats and mutually linked policy lineage together.
    # Deleting author seats first would strand policy-version references mid-command.
    ClassEconomy.query.filter_by(class_id=class_id).delete(synchronize_session=False)

    # Principals that held a seat only in this class are now parentless and must
    # not survive the scope that gave them existence. The teacher who owns the
    # class is protected by the ownership check inside the sweep; they are
    # destroyed only through FEAT-IDEN-007.
    # The acting principal is never swept here: for single-class destruction they
    # survive the class, and for account destruction FEAT-IDEN-007 removes them
    # explicitly once every owned class is gone.
    acting_user_id = getattr(canonical_context, "user_id", None)
    _delete_orphan_students(
        [sid for sid in scoped_student_ids if sid != acting_user_id]
    )


def _delete_teacher_residual_ownership_rows(canonical_context):
    """Delete teacher-user link rows not already removed by class-scoped deletion."""
    user_id = canonical_context.user_id
    # SQLAlchemy forbids bulk delete() on a joined query; scope through a
    # subquery instead (same pattern as the settings/activity deletions below).
    owned_class_ids_subq = db.session.query(ClassEconomy.class_id).filter(
        ClassEconomy.teacher_user_id == user_id
    ).subquery()
    Seat.query.filter(
        Seat.class_id.in_(sa.select(owned_class_ids_subq))
    ).delete(synchronize_session=False)


def _delete_teacher_settings_activity_and_audit_rows(canonical_context):
    """Delete teacher-user scoped settings, activity, and audit rows."""
    user_id = canonical_context.user_id
    class_ids_subq = db.session.query(ClassEconomy.class_id).filter(
        ClassEconomy.teacher_user_id == user_id
    ).subquery()
    HallPassSettings.query.filter(
        HallPassSettings.class_id.in_(sa.select(class_ids_subq))
    ).delete(synchronize_session=False)
    PayrollSettings.query.filter(
        PayrollSettings.class_id.in_(sa.select(class_ids_subq))
    ).delete(synchronize_session=False)
    Announcement.query.filter(
        Announcement.class_id.in_(sa.select(class_ids_subq))
    ).delete(synchronize_session=False)
    PendingAction.query.filter(
        PendingAction.authoritative_feat == "FEAT-STOR-002",
        PendingAction.class_id.in_(sa.select(class_ids_subq)),
    ).delete(synchronize_session=False)


def _delete_teacher_rent_rows(canonical_context):
    """Delete rent settings and dependent items owned by the teacher user."""
    user_id = canonical_context.user_id
    class_ids_subq = db.session.query(ClassEconomy.class_id).filter(
        ClassEconomy.teacher_user_id == user_id
    ).subquery()
    RentSettings.query.filter(
        RentSettings.class_id.in_(sa.select(class_ids_subq))
    ).delete(synchronize_session=False)


def _delete_teacher_insurance_rows(canonical_context):
    """Delete insurance policies and dependent rows scoped to classes owned by the teacher user."""
    user_id = canonical_context.user_id
    class_ids_subq = db.session.query(ClassEconomy.class_id).filter(
        ClassEconomy.teacher_user_id == user_id
    ).subquery()
    # Insurance tables are removed in v2; no legacy cleanup path remains here.
    _ = class_ids_subq


def _delete_teacher_issue_rows(canonical_context):
    """Delete issue records belonging to classes owned by this teacher.

    Issues are scoped by class_public_id matching the teacher's classes.
    """
    user_id = canonical_context.user_id
    class_public_ids = [
        pub_id for (pub_id,) in
        db.session.query(ClassEconomy.class_public_id).filter(ClassEconomy.teacher_user_id == user_id).all()
    ]
    if not class_public_ids:
        return
    issue_ids_subq = db.session.query(Issue.id).filter(
        Issue.class_public_id.in_(class_public_ids)
    ).subquery()
    IssueResolutionAction.query.filter(
        IssueResolutionAction.issue_id.in_(sa.select(issue_ids_subq))
    ).delete(synchronize_session=False)
    IssueStatusHistory.query.filter(
        IssueStatusHistory.issue_id.in_(sa.select(issue_ids_subq))
    ).delete(synchronize_session=False)
    Issue.query.filter(Issue.class_public_id.in_(class_public_ids)).delete(synchronize_session=False)


def _delete_teacher_recovery_and_credentials_rows(canonical_context):
    """Delete teacher-user recovery and credential rows."""
    user_id = canonical_context.user_id
    delete_recovery_rows_for_user(user_id)
    delete_admin_credentials_for_user(user_id)



def _delete_orphan_students(affected_student_ids):
    """Delete principals left with no seat in any class after a teardown.

    ``affected_student_ids`` is the set of users who held a seat in a scope that
    was just destroyed. Any of them with no remaining seat anywhere must be
    removed entirely — a ``users`` row has no standalone existence and carries
    credential material (INV-CORE-000 §III.5, DOM-IDEN-001 §VI).
    """
    if not affected_student_ids:
        return
    delete_orphaned_users(affected_student_ids)


def _destroy_teacher_account_rows(*, canonical_context, admin_user=None):
    """Terminal destruction of a teacher principal and everything it owns.

    Public FEAT entry (FEAT-IDEN-007). One envelope covers the whole command:
    every owned class universe is destroyed through the ``_destroy_class_scope_rows``
    *domain command*, then the account-level residue (settings, credentials,
    recovery material, the ``users`` row itself). The class destruction is
    composed, not delegated to FEAT-CLASS-006 — a FEAT never executes another
    FEAT (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2), and a single envelope is what
    makes the whole account teardown one atomic transaction.

    Authority is the canonical context alone; no display value or alias
    participates in resolving what gets destroyed (INV-CORE-000 §III.4).
    """
    if canonical_context is None or not getattr(canonical_context, "user_id", None):
        raise ValueError("canonical_context is required for account deletion")
    user_id = canonical_context.user_id

    class_ids = [
        value for (value,) in db.session.query(ClassEconomy.class_id).filter(
            ClassEconomy.teacher_user_id == user_id,
        ).distinct().all()
    ]

    affected_student_ids = {
        sid for (sid,) in db.session.query(Seat.user_id)
        .filter(Seat.class_id.in_(class_ids), Seat.user_id.isnot(None))
        .distinct()
        .all()
    }
    # The teacher may hold a seat in their own class. Their principal is removed
    # explicitly at the end of this command, not by the orphan sweep.
    affected_student_ids.discard(user_id)

    # Required ordering: all class-scoped data is destroyed before the account rows.
    for class_id in class_ids:
        _destroy_class_scope_rows(
            class_id=class_id,
            canonical_context=canonical_context,
        )

    _delete_teacher_residual_ownership_rows(canonical_context)
    _delete_teacher_settings_activity_and_audit_rows(canonical_context)
    _delete_teacher_rent_rows(canonical_context)
    _delete_teacher_insurance_rows(canonical_context)
    _delete_teacher_issue_rows(canonical_context)
    _delete_teacher_recovery_and_credentials_rows(canonical_context)
    _delete_orphan_students(affected_student_ids)

    # The principal itself. Terminal — the users row does not survive.
    admin_user = db.session.get(User, user_id)
    if admin_user is not None:
        delete_admin_account_rows(admin_user)
