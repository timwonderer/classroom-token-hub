"""WCAG 2.1 A/AA audit of Group D: pages that need a real, already-existing
domain row (an insurance claim mid-review, a filed issue, an active policy, a
specific student's detail view, an announcement in edit mode) rather than one
built fresh in a hermetic test run. See tests/simulated/conftest.py for why
this directory runs against a persistent, production-sourced world instead of
the per-test-run schema tests/test_axe_app_pages.py uses for Groups A/B/C/E-H.

The anchor class, its two seats, and every per-page row this file needs
(announcement, claim, issue, active policy entitlement) are all resolved
find-or-create at run time: query the world first, and create through the
real FEAT/route/production-service-function only when nothing matches,
contributing the result back for next time -- the same convention
tests/test_axe_app_pages.py uses for the hermetic groups. This file holds no
hard-coded assumption about what, if anything, the world already contains.

That matters here specifically: this file originally hard-coded its anchor
as "Rabbit Hole 101" (class_id 6135423f-80cf-43ec-9ce3-4e05ffb98fad, teacher
seat 1, student seat 3), found once by querying the world
directly (see docs/ops/audits/ for the mapping that sorted every template
into a group). That entire class -- including both seats, not just its
issue/claims/hall-pass-log -- was deleted by mistake during 2026-11 test-DB
migration work (see docs/ops/audits/ and CHANGELOG.md) after being
misidentified as orphaned junk. It was not recoverable: this world is seeded
once from a production snapshot and never rebuilt (tests/simulated/
conftest.py), and no local backup existed. Every hard-coded id in this file
(CLASS_ID, TEACHER_SEAT_ID, STUDENT_SEAT_ID, STUDENT_PUBLIC_ID, ISSUE_ID,
POLICY_UUID) broke as a result. They have all been replaced with
find-or-create resolution (_find_or_create_anchor_classroom(),
_find_or_create_issue(), _find_or_create_active_policy_uuid(), alongside the
pre-existing _find_or_create_announcement()/_find_or_create_claim()) so a
future loss of any of these rows -- even the whole anchor class -- self-heals
on the next run instead of needing another incident.
"""

from __future__ import annotations

import re
from decimal import Decimal
from uuid import uuid4

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.class_configuration import configure_insurance_definition
from app.feats.insurance_claim_feat import (
    InsuranceClaimPolicyError,
    describe_claim_contract,
    submit_insurance_claim,
)
from app.feats.purchase_insurance_feat import execute_purchase_insurance
from app.models import Announcement, EntitlementEvent, InsuranceClaim, InsurancePolicy, Seat
from app.services.context_resolver import CanonicalContext
from app.utils.issue_categories import get_active_categories, init_default_categories
from app.utils.issue_helpers import create_issue
from app.utils.opaque_refs import make_opaque_ref
from tests.helpers.axe_wcag import (
    assert_no_violations,
    authenticated_page,
    axe_violations,
    sync_playwright,
    teacher_session as _build_teacher_session,
    student_session as _build_student_session,
    wcag_live_server,  # noqa: F401 -- fixture, used via pytest injection
)
from tests.helpers.ledger import create_ledger_idempotent_transaction
from tests.helpers.support_domain import create_class_announcement

# Resolved at test run time by _find_or_create_anchor_classroom(), not
# hard-coded: this persistent world's rows are not a reproducible fixture
# (tests/simulated/conftest.py -- seeded once from a production snapshot,
# never rebuilt), so a literal class_id/seat_id/public_id here is a single
# point of failure if that row is ever lost. Same for ISSUE_ID and
# POLICY_UUID, resolved by _find_or_create_issue() and
# _find_or_create_active_policy_uuid() -- query first, create through the
# real FEAT/route only when nothing matches, exactly as
# _find_or_create_announcement()/_find_or_create_claim() already do.
CLASS_ID: str
TEACHER_SEAT_ID: int
STUDENT_SEAT_ID: int
STUDENT_PUBLIC_ID: str

ANCHOR_DISPLAY_NAME = "Group D Accessibility Fixture"


def _find_or_create_anchor_classroom() -> tuple[str, int, int, str]:
    """The (class_id, teacher_seat_id, student_seat_id, student_public_id)
    this file's tests run against.

    Reuses a previously-provisioned Group D anchor classroom when this
    persistent world already has one (tagged by ANCHOR_DISPLAY_NAME), or
    provisions a fresh one -- through the same production service functions
    tests/simulated/test_group_l_pages.py uses for its own anchor classroom
    (create_teacher, create_class, _provision_roster_seat,
    create_student_user_for_seat), never hand-assembled ORM rows -- when none
    exists yet. Unlike Group J/L, Group D has no reason to always mint a
    fresh classroom (nothing here needs a plaintext username recovered
    later), so reusing one keeps this file's provisioning cost down the way
    the announcement/claim/issue/policy helpers below already do for rows
    within the class.
    """
    from app.models import ClassEconomy, Seat

    # Search every matching class, not just the first: an earlier interrupted
    # run can leave an incomplete anchor (same display_name, no student user)
    # behind in this persistent world, and a naive .first() could keep
    # re-selecting that same incomplete row forever -- discarding it and
    # minting a fresh replacement on every run instead of ever converging on
    # a completed one.
    existing = None
    teacher_seat = student_seat = None
    for candidate in ClassEconomy.query.filter_by(display_name=ANCHOR_DISPLAY_NAME).order_by(
        ClassEconomy.class_id.asc()
    ):
        candidate_teacher_seat = Seat.query.filter_by(class_id=candidate.class_id, role="teacher").first()
        # Filter for a claimed seat (user_id set) here rather than after: an
        # unclaimed seat ordered ahead of a claimed one would otherwise make
        # this candidate look incomplete even though a usable seat exists.
        candidate_student_seat = (
            Seat.query.filter_by(class_id=candidate.class_id, role="student")
            .filter(Seat.user_id.isnot(None))
            .order_by(Seat.id.asc())
            .first()
        )
        if candidate_teacher_seat is not None and candidate_student_seat is not None:
            existing, teacher_seat, student_seat = candidate, candidate_teacher_seat, candidate_student_seat
            break  # first complete anchor found -- reuse it

    if existing is None:
        from app.feats.base import FEATContext
        from app.services.classroom_setup import create_class, create_student_user_for_seat, create_teacher
        from app.utils.join_code import generate_join_code
        from app.utils.username_generation import build_username
        from tests.helpers.canonical_classroom import _provision_roster_seat
        from tests.helpers.canonical_identities import CLASSROOMS

        roster_row = CLASSROOMS["chemistry_p1"]["roster"][0]
        teacher_username = f"teacher.axe-group-d.{uuid4().hex[:12]}"

        # No explicit app_context() here: this helper is only ever called from
        # the test function below, inside the ambient context the app/client
        # fixtures already establish -- opening and exiting a second, nested
        # app_context() here would detach these ORM instances from the session
        # before this function returns them.
        join_code = generate_join_code()
        with FEATContext("FEAT-IDEN-001", idempotency_key=f"axe-sweep:group-d:{teacher_username}"):
            teacher_user = create_teacher(teacher_username)
            existing = create_class(
                teacher_user.id, join_code=join_code,
                display_name=ANCHOR_DISPLAY_NAME, section="Accessibility",
                class_timezone="America/Los_Angeles",
            )
            teacher_seat = Seat.query.filter_by(class_id=existing.class_id, role="teacher").one()
            student_seat = _provision_roster_seat(existing.class_id, roster_row)
            username = build_username(roster_row["chosen_word"], student_seat.roster_fingerprint or "")
            create_student_user_for_seat(
                student_seat, username=username, pin=roster_row["pin"], passphrase=roster_row["passphrase"],
            )
        db.session.commit()

    # student.file_claim/view_policy 404 (app/routes/student.py's
    # enforce_student_feature_gates) unless 'insurance' is enabled for the
    # class -- the original anchor already had it on; a freshly-provisioned
    # (or partially-provisioned, from an earlier interrupted run) class may
    # not, so this is checked and fixed on every call, not just on creation.
    from app.services.class_configuration_query_service import is_feature_enabled as _class_feature_enabled
    if not _class_feature_enabled(existing.class_id, "insurance"):
        from tests.helpers.class_domain import enable_class_feature
        enable_class_feature(class_id=existing.class_id, feature="insurance")

    return existing.class_id, teacher_seat.id, student_seat.id, student_seat.public_id


def _user_id_of(seat_id: int) -> str:
    """The principal bound to a fixed world seat. users.id is a random UUID
    (f4b8d2a6c1e9), so it is read from the seat rather than hard-coded."""
    from app.models import Seat
    seat = Seat.query.filter_by(id=seat_id, class_id=CLASS_ID).one()
    return seat.user_id


def _find_or_create_announcement(client) -> int:
    """The world had zero announcements for this class as of 2026-09-23.
    Query first; only create (through the real admin route, as a real
    teacher submission) when nothing matches -- contributing the row back to
    the persistent world for next time, per this directory's own convention.
    """
    existing = Announcement.query.filter_by(class_id=CLASS_ID).first()
    if existing is not None:
        return existing.id

    response = create_class_announcement(
        client,
        title="Group D Accessibility Fixture Announcement",
        message="Seeded by tests/simulated/test_group_d_pages.py so the "
        "announcement-edit page has a real row to render.",
        priority="normal",
        is_active=True,
    )
    assert response.status_code == 200, response.data

    created = Announcement.query.filter_by(class_id=CLASS_ID).first()
    assert created is not None, "announcement_create did not persist a row"
    return created.id


# A policy this file adds to the world when no reviewable claim exists yet.
FIXTURE_POLICY_TITLE = "Group D Accessibility Fixture Cover"


def _teacher_ctx() -> CanonicalContext:
    return CanonicalContext(
        user_id=_user_id_of(TEACHER_SEAT_ID), class_id=CLASS_ID, seat_id=TEACHER_SEAT_ID, actor_role="teacher",
    )


def _student_ctx() -> CanonicalContext:
    return CanonicalContext(
        user_id=_user_id_of(STUDENT_SEAT_ID), class_id=CLASS_ID, seat_id=STUDENT_SEAT_ID, actor_role="student",
    )


def _is_reviewable(claim) -> bool:
    """Whether the admin review page can resolve this claim's contract.

    Claims filed before insurance premiums were keyed by entitlement
    (FEAT-STOR-007) have no coverage period to be judged in, so the review
    page refuses them. Only claims filed under the current model qualify.
    """
    try:
        describe_claim_contract(claim, canonical_context=_teacher_ctx())
    except InsuranceClaimPolicyError:
        return False
    return True


def _fixture_policy_uuid() -> str:
    existing = InsurancePolicy.query.filter_by(
        class_id=CLASS_ID, title=FIXTURE_POLICY_TITLE
    ).first()
    if existing is not None:
        return existing.policy_uuid
    policy_uuid = configure_insurance_definition(
        class_id=CLASS_ID,
        submission=dict(
            insurance_type="TRANSACTION", premium="1.00", charge_frequency="WEEKLY",
            reimbursement_percentage="100", payout_multiple="5",
            claims_per_week_equivalent="1", claim_window_days="7",
            bill_preview_days=3, nonpayment_mode="ACCUMULATE", title=FIXTURE_POLICY_TITLE,
        ),
        canonical_context=_teacher_ctx(),
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"FEAT-CLASS-003:configure:{uuid4().hex}",
    ).policy_uuid
    db.session.commit()
    return policy_uuid


def _fund_and_purchase_fixture_policy(policy_uuid: str):
    """Fund the anchor student's checking account and purchase ``policy_uuid``
    for them through the real FEAT, returning the purchase result (which
    carries the new entitlement_id). Shared by ``_find_or_create_claim`` and
    ``_find_or_create_active_policy_uuid`` so both end up with an active,
    FEAT-created entitlement rather than two divergent code paths.
    """
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"groupd:fund:{uuid4().hex}"):
        create_ledger_idempotent_transaction(
            idempotency_key=f"groupd:fund:{uuid4().hex}", seat_id=STUDENT_SEAT_ID,
            class_id=CLASS_ID, amount=Decimal("5.00"), account_type="checking",
            type="payroll", description="Group D fixture: premium funding",
        )
    db.session.commit()
    purchase = execute_purchase_insurance(
        canonical_context=_student_ctx(), policy_uuid=policy_uuid,
        idempotency_key=f"groupd:buy:{uuid4().hex}",
    )
    db.session.commit()
    assert purchase.success, purchase.error_message
    return purchase


def _active_entitlement_id(policy_uuid: str) -> str | None:
    """The anchor student's unterminated INSURANCE entitlement id under
    ``policy_uuid``, if one exists: an entitlement lineage with a GRANTED
    event and no later CONSUMED/EXPIRED/REVOKED event. ``policy_uuid`` is
    frozen in ``payload``, not a column, so this reads it back in Python the
    way ``app/services/store_service.py:resolve_entitlement_product`` does.
    """
    events = (
        EntitlementEvent.query.filter_by(
            class_id=CLASS_ID, target_seat_id=STUDENT_SEAT_ID, entitlement_type="INSURANCE",
        )
        .order_by(EntitlementEvent.timestamp.asc())
        .all()
    )
    granted_lineages = {
        e.entitlement_id for e in events
        if e.event_type == "GRANTED" and (e.payload or {}).get("policy_uuid") == policy_uuid
    }
    if not granted_lineages:
        return None
    terminated_lineages = {e.entitlement_id for e in events if e.event_type in ("CONSUMED", "EXPIRED", "REVOKED")}
    active = granted_lineages - terminated_lineages
    return next(iter(active), None)


def _has_active_entitlement(policy_uuid: str) -> bool:
    return _active_entitlement_id(policy_uuid) is not None


def _find_or_create_active_policy_uuid() -> str:
    """A policy_uuid under which the anchor student holds active (GRANTED,
    not yet CONSUMED/EXPIRED/REVOKED) coverage -- required for
    student.file_claim/student.view_policy to render a form instead of
    redirecting with a flash ("you don't hold active coverage"). Reuses the
    fixture policy's existing entitlement when one is still active; purchases
    a fresh one via the real FEAT otherwise.
    """
    policy_uuid = _fixture_policy_uuid()
    if not _has_active_entitlement(policy_uuid):
        _fund_and_purchase_fixture_policy(policy_uuid)
    return policy_uuid


def _find_or_create_issue(app, client) -> int:
    """An issue visible to both admin.view_issue (requires student-authored,
    app/services/support_operator_access.py's student_authored_clause) and
    sysadmin.view_issue (requires escalated OR teacher-authored,
    sysadmin_visible_clause) -- the two pages this file audits with the same
    ref. Those are only simultaneously true for a student-authored issue the
    teacher has escalated, so this files one through the real FEAT-SUP-001
    helper if none exists yet, then escalates it through the real
    /admin/issues/<ref>/escalate route (admin.escalate_issue) if it isn't
    already.
    """
    from app.models import Issue

    # admin.escalate_issue (app/routes/admin.py) only escalates a ticket whose
    # status is OPEN/TEACHER_REVIEW ('submitted'/'teacher_review'); a resolved
    # or closed one is rejected. Picking the student's oldest issue
    # unconditionally can land on exactly such a ticket even when a newer,
    # already-escalated or still-escalatable one exists -- prefer one that
    # already qualifies over blindly taking the oldest.
    escalatable_statuses = {Issue.STATUS_OPEN, Issue.STATUS_TEACHER_REVIEW, 'submitted', 'teacher_review'}
    seat = Seat.query.filter_by(id=STUDENT_SEAT_ID, class_id=CLASS_ID).one()
    # Scope to this fixture's own explanation text, not every issue the anchor
    # seat happens to have: the anchor seat is dedicated to this file, but an
    # unrelated issue filed against it (manual testing, another tool) should
    # never get escalated by this test as a side effect of running it.
    candidates = (
        Issue.query.filter_by(
            actor_public_id=seat.public_id, student_explanation="Group D accessibility fixture issue.",
        )
        .order_by(Issue.id.asc())
        .all()
    )
    issue = next((i for i in candidates if i.escalated_at is not None), None)
    if issue is None:
        issue = next((i for i in candidates if i.status in escalatable_statuses), None)
    if issue is None:
        categories = get_active_categories("general")
        if not categories:
            init_default_categories(
                correlation_id=f"corr_{uuid4().hex}", idempotency_key=f"groupd:categories:{uuid4().hex}",
            )
            db.session.commit()
            categories = get_active_categories("general")
        category_id = categories[0][0]

        # create_issue reads flask.request (for page_url) outside of any route
        # handler here, so give it one the same way tests/test_open_redirect_hardening.py
        # and others in this repo do for a direct FEAT call outside a real request.
        with app.test_request_context("/student/help-support/submit-issue"):
            issue = create_issue(
                actor=seat, user_id=seat.user_id, class_id=CLASS_ID, category_id=category_id,
                explanation="Group D accessibility fixture issue.",
                expected_outcome="A reviewable issue exists for the admin/sysadmin view pages.",
                include_recent_error=False,
                correlation_id=f"corr_{uuid4().hex}",
                idempotency_key=f"groupd:issue:{uuid4().hex}",
            )
            db.session.commit()

    if issue.escalated_at is None:
        response = client.post(
            f"/admin/issues/{make_opaque_ref('issue', issue.id)}/escalate",
            data={
                "escalation_reason": "Group D accessibility fixture: escalated so sysadmin.view_issue has a real row.",
                "diagnostic_note": "",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200, response.data
        issue = Issue.query.get(issue.id)
        assert issue.escalated_at is not None, "escalate_issue did not set escalated_at"

    return issue.id


def _find_or_create_claim() -> str:
    """A pending claim the admin review page can render, created via FEATs if none exists.

    Created once: buy the fixture policy for the anchor student, record a loss,
    and file a TRANSACTION claim against it. The claim stays reviewable on every
    later run, because the coverage period it was filed in is recorded history.
    """
    for claim in (
        InsuranceClaim.query.filter_by(class_id=CLASS_ID, target_seat_id=STUDENT_SEAT_ID)
        .order_by(InsuranceClaim.submitted_at.desc())
        .all()
    ):
        if _is_reviewable(claim):
            return claim.claim_id

    policy_uuid = _fixture_policy_uuid()
    entitlement_id = _active_entitlement_id(policy_uuid)
    if entitlement_id is None:
        purchase = _fund_and_purchase_fixture_policy(policy_uuid)
        entitlement_id = purchase.entitlement_id

    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"groupd:loss:{uuid4().hex}"):
        loss, _ = create_ledger_idempotent_transaction(
            idempotency_key=f"groupd:loss:{uuid4().hex}", seat_id=STUDENT_SEAT_ID,
            class_id=CLASS_ID, amount=Decimal("-2.00"), account_type="checking",
            type="purchase", description="Group D fixture: covered loss",
        )
        loss_id = loss.id
    db.session.commit()
    filed = submit_insurance_claim(
        canonical_context=_student_ctx(), entitlement_id=entitlement_id,
        claim_subject={"transaction_id": loss_id}, correlation_id=f"claim:{uuid4().hex}",
    )
    db.session.commit()
    assert filed.success, filed.error_message
    return filed.claim_id


def _scrape_student_detail_url(client) -> str:
    """The student-detail route requires a server-signed ``nav`` token minted
    per-request by the admin.students page itself (app/routes/admin.py's
    ``student_detail_url`` template global) -- it cannot be hand-built, so we
    make a real GET request as the teacher and scrape the real link out of
    the rendered HTML, exactly as a browser would follow it.
    """
    response = client.get("/admin/students")
    assert response.status_code == 200, response.data
    html = response.get_data(as_text=True)
    match = re.search(
        r'href="(/admin/students/' + re.escape(STUDENT_PUBLIC_ID) + r'\?nav=[^"]+)"',
        html,
    )
    assert match is not None, "could not find a nav-token link for the target student"
    return match.group(1).replace("&amp;", "&")


@pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")
def test_no_axe_violations_across_group_d_pages(app, client, wcag_live_server):
    """WCAG 2.1 A/AA audit of Group D: admin_process_claim, admin_view_issue,
    sysadmin_view_issue, student_file_claim, student_view_policy,
    admin_announcement_form (edit mode), and student_detail.
    """
    global CLASS_ID, TEACHER_SEAT_ID, STUDENT_SEAT_ID, STUDENT_PUBLIC_ID
    CLASS_ID, TEACHER_SEAT_ID, STUDENT_SEAT_ID, STUDENT_PUBLIC_ID = _find_or_create_anchor_classroom()

    teacher_session = _build_teacher_session(
        client, user_id=_user_id_of(TEACHER_SEAT_ID), class_id=CLASS_ID, seat_id=TEACHER_SEAT_ID,
    )

    announcement_id = _find_or_create_announcement(client)
    claim_id = _find_or_create_claim()
    policy_uuid = _find_or_create_active_policy_uuid()
    student_detail_path = _scrape_student_detail_url(client)
    # admin.view_issue accepts either a plain numeric id or the encrypted
    # opaque ref; sysadmin.view_issue accepts only the opaque ref (its own
    # _resolve_issue_id_from_ref has no digit-string fast path) -- use the
    # opaque form for both so one ref works everywhere.
    issue_ref = make_opaque_ref("issue", _find_or_create_issue(app, client))

    # sysadmin_session isn't needed here: sysadmin_view_issue is reachable
    # with a plain sysadmin session dict the same way tests/test_axe_app_pages.py
    # builds one, but this file's teacher/student anchor class already
    # supplies everything else -- build it locally to avoid a second helper
    # import cycle.
    from tests.helpers.axe_wcag import sysadmin_session as _build_sysadmin_session

    admin_session = _build_sysadmin_session("axe_sweep_group_d_sysadmin")

    student_session = _build_student_session(
        client, user_id=_user_id_of(STUDENT_SEAT_ID), class_id=CLASS_ID, seat_id=STUDENT_SEAT_ID,
    )

    pages: list[tuple[str, dict | None]] = [
        (f"/admin/insurance/claim/{claim_id}", teacher_session),
        (f"/admin/issues/{issue_ref}", teacher_session),
        (student_detail_path, teacher_session),
        (f"/admin/announcements/edit/{announcement_id}", teacher_session),
        (f"/sysadmin/issues/{issue_ref}", admin_session),
        (f"/student/insurance/claim/{policy_uuid}", student_session),
        (f"/student/insurance/policy/{policy_uuid}", student_session),
    ]

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            pytest.skip(f"Chromium is unavailable: {exc}")

        with browser:
            failures: dict[str, list] = {}
            for path, session_dict in pages:
                page = authenticated_page(browser, wcag_live_server, session_dict)
                violations = axe_violations(page, f"{wcag_live_server}{path}")
                if violations:
                    failures[path] = violations
                page.context.close()

            assert_no_violations(failures)
