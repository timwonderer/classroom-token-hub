from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.admin_adjustment_feat import execute_admin_adjustments
from app.models import IdentityProfile, Issue, IssueCategory, Seat, Transaction, TransactionStatus
from app.models import User, UserRole
from app.services.classroom_setup import create_student_seat_with_profile
from app.services.context_resolver import CanonicalContext
from app.utils.auth_username import build_hashed_username_fields
from tests.helpers.classroom_initializer import initialize, initialize_as_student, initialize_as_teacher
from tests.helpers.operation_routes import seed_sysadmin_session


def teacher_issue_lifecycle(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with FEATContext("FEAT-ADMN-001", idempotency_key="issue_lifecycle:seed"):
        category = IssueCategory(
            name="Lifecycle Category",
            category_type="general",
            is_active=True,
        )
        db.session.add(category)
        db.session.flush()
        issue = Issue(
            actor_public_id=classroom.students[0].seat.public_id,
            class_public_id=classroom.economy.class_public_id,
            category_id=category.id,
            issue_type="general",
            student_explanation="Balance looked incorrect after store purchase.",
            status=Issue.STATUS_TEACHER_REVIEW,
        )
        db.session.add(issue)
        db.session.flush()
    return classroom, issue


def payroll_visibility_state(client, app):
    """Shared-user, multi-class earnings scoping fixture.

    One User owns claimed seats in two different classes (under different
    teachers so neither provisioning step repoints the logged-in student's
    context):
      - seat_a in class_a (chemistry_p1): $10.00 payroll earnings
      - seat_b in class_b (biology_block_a): $200.00 payroll earnings

    The student is logged in and active in class_a. Per DOM-LED-001, displayed
    earnings are scoped to the active seat/class, so the class_a payroll and
    transfer pages must show $10.00 (seat_a only) and must NOT aggregate to
    $210.00 across the user's seats in other classes.
    """
    classroom_a, student_a = initialize_as_student("chemistry_p1", client, app)
    classroom_b = initialize("biology_block_a", app)

    # Seat provisioning for class_b uses the canonical production producer
    # (create_student_seat_with_profile), the same path the roster/import flows
    # use to materialize a class-scoped student seat + IdentityProfile.
    #
    # GAP (reported, not silently substituted): there is no standalone canonical
    # producer that BINDS an already-authenticated User to an additional class's
    # seat. The claim flow (identity_feat.resolve_seat_claim) intentionally
    # creates a NEW user per DOM-IDEN-005 §VII and must not infer existing
    # identities; the only binding path (create_student_user_for_seat) also
    # mints a new User. Binding the SAME user to a second class therefore has no
    # production entry point, so the single `seat_b.user_id = ...` assignment
    # below is a direct field-set that mirrors what create_student_user_for_seat
    # does internally (classroom_setup.py:209). This is the sole ORM write in
    # this fixture; both earnings rows are posted through the canonical FEAT.
    with FEATContext("FEAT-IDEN-001", idempotency_key="payroll_visibility:shared_seat"):
        seat_b = create_student_seat_with_profile(
            class_id=classroom_b.class_id,
            first_name=student_a.first_name,
            last_name=student_a.last_name,
            claimed_at=datetime.now(timezone.utc),
        )
        seat_b.user_id = student_a.user.id  # GAP: no canonical binding producer.
        db.session.flush()

    # Earnings are posted through the LOWEST canonical ledger boundary
    # (execute_admin_adjustments → create_pending_transaction). A positive
    # amount posts a pending earnings transaction without touching attendance,
    # payroll cycles, or interest machinery. The read path
    # (_get_total_earnings_for_seat) counts pending rows, so this is a faithful
    # class-scoped earnings producer.
    ctx_a = CanonicalContext(
        user_id=classroom_a.teacher_user.id,
        class_id=classroom_a.class_id,
        seat_id=classroom_a.teacher_seat.id,
        actor_role="teacher",
    )
    ctx_b = CanonicalContext(
        user_id=classroom_b.teacher_user.id,
        class_id=classroom_b.class_id,
        seat_id=classroom_b.teacher_seat.id,
        actor_role="teacher",
    )
    with FEATContext("FEAT-LED-001", idempotency_key="payroll_visibility:seed_a"):
        # $10.00 earned in the active class (seat_a).
        execute_admin_adjustments(
            ctx=ctx_a,
            adjustments=[{
                "seat": student_a.seat,
                "user_id": classroom_a.teacher_user.id,
                "amount": Decimal("10.00"),
                "account_type": "checking",
                "type": "payroll",
                "description": "Payroll for class A",
            }],
            actor_seat_id=classroom_a.teacher_seat.id,
        )
    with FEATContext("FEAT-LED-001", idempotency_key="payroll_visibility:seed_b"):
        # $200.00 earned by the SAME user in another class (seat_b). Must not
        # appear in the class_a-scoped earnings display.
        execute_admin_adjustments(
            ctx=ctx_b,
            adjustments=[{
                "seat": seat_b,
                "user_id": classroom_b.teacher_user.id,
                "amount": Decimal("200.00"),
                "account_type": "checking",
                "type": "payroll",
                "description": "Payroll for class B",
            }],
            actor_seat_id=classroom_b.teacher_seat.id,
        )
    db.session.commit()
    return classroom_a, classroom_b


def _seed_reverse_category(idempotency_key: str) -> IssueCategory:
    """Create a transaction-type IssueCategory for reversal scenarios."""
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=idempotency_key):
        category = IssueCategory(
            name=f"Issue Reverse Category {datetime.now(timezone.utc).isoformat()}",
            category_type="transaction",
            is_active=True,
        )
        db.session.add(category)
        db.session.flush()
    return category


def unused_store_purchase(classroom, student, *, key: str, price: str = "30.00") -> Transaction:
    """A funded seat buys one delayed-use item and has not used it.

    This is the only transaction an issue may REVERSE or REFUND: FEAT-LED-002 §I
    resolves an eligible pre-use Store purchase, and SPEC-OPS-001 §3.7 makes
    everything else ineligible by default.
    """
    from app.feats.store_purchase_feat import execute_store_purchase
    from tests.helpers.ledger import create_ledger_idempotent_transaction
    from tests.helpers.store_products import publish_store_product

    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"{key}:fund"):
        create_ledger_idempotent_transaction(
            idempotency_key=f"{key}-fund",
            seat_id=student.seat.id,
            class_id=classroom.class_id,
            user_id=student.user.id,
            amount=Decimal("100.00"),
            account_type="checking",
            type="payroll",
            description="Issue reversal test funding",
        )
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"{key}:publish"):
        product = publish_store_product(
            class_id=classroom.class_id,
            entitlement_type="DELAYED_USE",
            user_id=classroom.teacher_user.id,
            name=f"Issue item {key}",
            price=price,
        )
    db.session.commit()
    result = execute_store_purchase(
        canonical_context=CanonicalContext(
            user_id=student.user.id,
            class_id=classroom.class_id,
            seat_id=student.seat.id,
            actor_role="student",
        ),
        policy_uuid=product.policy_uuid,
        quantity=1,
        idempotency_key=f"{key}:buy",
    )
    assert result.success, result.error_message
    db.session.commit()
    return (
        Transaction.query.filter_by(
            class_id=classroom.class_id, seat_id=student.seat.id, type="purchase",
        )
        .order_by(Transaction.id.desc())
        .first()
    )


def issue_for_transaction(classroom, student, tx, *, key: str) -> Issue:
    """The submitting student's issue about ``tx``."""
    category = _seed_reverse_category(f"{key}:category")
    with FEATContext("FEAT-LED-001", idempotency_key=f"{key}:issue"):
        issue = Issue(
            actor_public_id=student.seat.public_id,
            class_public_id=classroom.economy.class_public_id,
            category_id=category.id,
            issue_type="transaction",
            student_explanation="Please reverse this.",
            related_transaction_id=tx.id,
        )
        db.session.add(issue)
        db.session.flush()
    db.session.commit()
    return issue


def issue_reverse_success_state(client, app):
    """Success scenario: an unused Store purchase, in scope for the active teacher.

    - Active teacher class == the issue's class_public_id (issue is visible,
      passing the resolve route's class-scoped 404 gate).
    - The referenced purchase is owned by the issue submitter's seat
      (transaction.seat_id == submitter_seat.id) and its item is unused, so
      the reversal proceeds.

    Only one classroom is provisioned, so nothing repoints the teacher's
    last_active_class_id after login.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    tx = unused_store_purchase(classroom, student, key="issue_reverse_success")
    issue = issue_for_transaction(classroom, student, tx, key="issue_reverse_success")
    return classroom, student, issue, tx


def issue_reverse_scope_mismatch_state(client, app):
    """Scope-rejection scenario: the referenced transaction is not the
    submitter's.

    The teacher's active class stays stable and matches the issue's class, so
    the issue is fully visible (no 404). The rejection is caused solely by the
    intended ownership mismatch: the related transaction belongs to a DIFFERENT
    seat in the same class than the issue submitter, triggering the production
    guard `transaction.seat_id != submitter_seat.id`.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    submitter = classroom.students[0]
    other_student = classroom.students[1]
    category = _seed_reverse_category("issue_reverse_mismatch:category")

    with FEATContext("FEAT-LED-001", idempotency_key="issue_reverse_mismatch:posted_tx"):
        # Transaction is owned by other_student's seat, NOT the submitter's.
        tx = Transaction(
            user_id=other_student.user.id,
            class_id=classroom.class_id,
            seat_id=other_student.seat.id,
            target_seat_id=other_student.seat.id,
            actor_seat_id=other_student.seat.id,
            mechanism="self",
            amount=Decimal("30.00"),
            account_type="checking",
            status=TransactionStatus.POSTED,
            type="deposit",
            description="Posted deposit (other student)",
        )
        db.session.add(tx)
        db.session.flush()
        issue = Issue(
            actor_public_id=submitter.seat.public_id,
            class_public_id=classroom.economy.class_public_id,
            category_id=category.id,
            issue_type="transaction",
            student_explanation="Please reverse this.",
            related_transaction_id=tx.id,
        )
        db.session.add(issue)
        db.session.flush()
    db.session.commit()
    return classroom, submitter, other_student, issue, tx


def sysadmin_reward_issue_state(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    category = IssueCategory(
        name="Bug Report Category",
        category_type="general",
        is_active=True,
    )
    with FEATContext("FEAT-IDEN-001", idempotency_key="sysadmin_issue_reward:category"):
        db.session.add(category)
        db.session.flush()
    with FEATContext("FEAT-TEST-001", idempotency_key="sysadmin_issue_reward:issue"):
        issue = Issue(
            actor_public_id=student.seat.public_id,
            class_public_id=classroom.economy.class_public_id,
            category_id=category.id,
            issue_type="general",
            student_explanation="Found a reproducible bug in the app.",
            student_expected_outcome="Expected behavior should work.",
            status=Issue.STATUS_ESCALATED_TO_DEV,
            eligible_for_reward=True,
        )
        db.session.add(issue)
        db.session.flush()
    db.session.commit()
    return classroom, student, issue


def create_sysadmin(username: str = "sysadmin") -> User:
    """Provision a canonical sysadmin User (UserRole.SYSADMIN).

    The legacy `create-sysadmin` Flask CLI command was removed; sysadmin
    authority now lives entirely on User.user_role=SYSADMIN (app/models.py:292).
    Tests provision it directly through the canonical User model and authenticate
    via seed_sysadmin_session (tests/helpers/operation_routes.py), which mirrors
    the session shape the production /sysadmin/login route establishes — no CLI
    and no TOTP round-trip required.
    """
    _salt, u_hash, u_lookup = build_hashed_username_fields(username)
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"sysadmin_issue_reward:sysadmin:{username}"):
        user = User(
            user_role=UserRole.SYSADMIN,
            username_hash=u_hash,
            username_lookup_hash=u_lookup,
        )
        db.session.add(user)
        db.session.flush()
    db.session.commit()
    return user


def login_sysadmin(client, username: str, user_id: int) -> None:
    """Authenticate a provisioned sysadmin via the canonical session helper."""
    seed_sysadmin_session(client, user_id=user_id, username=username)
