"""Regressions for the functional defects found during the 2026-09-19 live test.

Each test here corresponds to a numbered finding in
``docs/ops/audits/LIVE_TEST_DEPLOYMENT_2026-09-19.md`` and fails against the
code as deployed at ``live-test/2026-09-19`` (SHA ``8c5cff7c8``). They are
grouped in one module because they share nothing except provenance: what makes
them worth keeping together is that every one of them was invisible to a
2,997-test suite and visible within minutes of a real browser.

Findings covered:

* **10** — immediate-use items were never consumed at sale.
* **12** — the redemption modal asked for a PIN and the server checked the
  passphrase.
* **13** — the Store offered a second hall-pass request path with no attendance
  precondition.
* **20** — the lawful hall-pass path required no credential at all.
* **6A** — teacher-entered dates were stored as UTC midnight, firing a day
  early for any class west of Greenwich.
"""

from __future__ import annotations

import inspect
from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest
import pytz

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.store_purchase_feat import execute_store_purchase
from app.models import ClassEconomy, EntitlementEvent, PendingAction, User
from app.services.context_resolver import CanonicalContext
from app.hash_utils import hash_password
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.ledger import create_ledger_idempotent_transaction
from tests.helpers.store_products import publish_store_product


@pytest.fixture
def buyer(app):
    """A funded student seat in a canonical class."""
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        student = classroom.students[0]
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"live-regr:fund:{student.seat_id}"):
            create_ledger_idempotent_transaction(
                idempotency_key=f"live-regr-fund:{student.seat_id}",
                seat_id=student.seat_id,
                class_id=classroom.class_id,
                amount=Decimal("500.00"),
                account_type="checking",
                type="payroll",
                description="Live-test regression funding",
            )
        db.session.commit()
        yield {
            "class_id": classroom.class_id,
            "teacher_seat_id": classroom.teacher_seat_id,
            "user_id": student.user_id,
            "seat_id": student.seat_id,
            "context": CanonicalContext(
                user_id=student.user_id,
                class_id=classroom.class_id,
                seat_id=student.seat_id,
                actor_role="student",
            ),
        }


def _publish(buyer, name, entitlement_type, **definition):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"live-regr:publish:{name}"):
        product = publish_store_product(
            class_id=buyer["class_id"],
            entitlement_type=entitlement_type,
            created_by_seat_id=buyer["teacher_seat_id"],
            name=name,
            **definition,
        )
    db.session.commit()
    return product


def _set_credentials(buyer, *, pin=None, passphrase=None):
    """Set credentials through a FEAT context, as any credential write must."""
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"live-regr:creds:{buyer['user_id']}"):
        user = db.session.get(User, buyer["user_id"])
        if pin is not None:
            user.pin_hash = hash_password(pin)
        if passphrase is not None:
            user.passphrase_hash = hash_password(passphrase)
    db.session.commit()


def _login_student(client, buyer):
    """Establish the student session the way production login does."""
    from tests.helpers.canonical_session import set_canonical_context

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=buyer["user_id"],
            class_id=buyer["class_id"],
            seat_id=buyer["seat_id"],
            role="student",
        )


def _events(buyer, product, event_type=None):
    query = db.session.query(EntitlementEvent).filter_by(
        class_id=buyer["class_id"],
        target_seat_id=buyer["seat_id"],
        product_id=product.product_lineage_uuid,
    )
    if event_type:
        query = query.filter_by(event_type=event_type)
    return query.all()


# ---------------------------------------------------------------------------
# Finding 10 — immediate use is consumed at sale
# ---------------------------------------------------------------------------


class TestImmediateUseIsConsumedAtSale:
    """SPEC-STORE-001 §III: "Granted and consumed in the same action"."""

    def test_immediate_use_purchase_writes_granted_and_consumed(self, app, buyer):
        with app.app_context():
            product = _publish(buyer, "Instant Snack", "IMMEDIATE_USE", price="5.00")

            result = execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=1,
            )
            assert result.success is True

            granted = _events(buyer, product, "GRANTED")
            consumed = _events(buyer, product, "CONSUMED")
            assert len(granted) == 1
            # The defect: CONSUMED was never written, so the item sat in My
            # Items behind a "Use Now" button the specification forbids.
            assert len(consumed) == 1, (
                "IMMEDIATE_USE must be consumed at sale; an unexercised "
                "IMMEDIATE_USE entitlement is a state SPEC-STORE-001 does not permit"
            )

    def test_grant_and_consumption_share_one_correlation_id(self, app, buyer):
        """One sale is one action, so both events carry one correlation."""
        with app.app_context():
            product = _publish(buyer, "Instant Sticker", "IMMEDIATE_USE", price="2.00")
            execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=1,
            )
            correlations = {e.correlation_id for e in _events(buyer, product)}
            assert len(correlations) == 1

    def test_delayed_use_is_not_consumed_at_sale(self, app, buyer):
        """The derivation must be narrow: only IMMEDIATE_USE is exercised at sale.

        Without this, a fix that consumed everything would pass the test above
        while destroying delayed-use items the student has not redeemed yet.
        """
        with app.app_context():
            product = _publish(buyer, "Raincheck", "DELAYED_USE", price="5.00")
            execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=1,
            )
            assert len(_events(buyer, product, "GRANTED")) == 1
            assert _events(buyer, product, "CONSUMED") == []

    def test_instant_use_is_not_a_caller_supplied_argument(self):
        """The signature is the fix.

        The defect was expressible only because ``instant_use`` was a caller
        argument defaulting to False that every call site forgot to set.
        Deriving it inside the FEAT removes the opportunity rather than
        patching the one caller that got it wrong, so the absence of the
        parameter is itself the regression guard.
        """
        signature = inspect.signature(execute_store_purchase)
        assert "instant_use" not in signature.parameters


# ---------------------------------------------------------------------------
# Findings 12 and 13 — credential boundary, and hall passes are not used here
# ---------------------------------------------------------------------------


class TestHallPassIsNotRedeemedFromTheStore:
    """DOM-PROD-001: exercising a pass marks a student out of an active session."""

    def test_use_item_refuses_a_hall_pass_and_points_at_the_break_flow(self, app, client, buyer):
        with app.app_context():
            product = _publish(buyer, "Corridor Pass", "HALL_PASS", price="3.00")
            execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=1,
            )
            granted = _events(buyer, product, "GRANTED")
            entitlement_id = granted[0].entitlement_id
            _set_credentials(buyer, passphrase="correct-horse-battery")

        _login_student(client, buyer)

        response = client.post(
            "/api/use-item",
            json={"entitlement_id": entitlement_id, "passphrase": "correct-horse-battery"},
        )

        assert response.status_code == 400
        assert b"Break" in response.data

        with app.app_context():
            # The defect wrote a PendingAction with no attendance precondition,
            # so a student who had never clocked in could request a pass.
            assert PendingAction.query.filter_by(entitlement_id=entitlement_id).count() == 0

    def test_purchasing_a_hall_pass_still_credits_the_balance(self, app, buyer):
        """Refusing redemption here must not cost the student the pass they bought."""
        from app.services.entitlement_service import get_hall_pass_balance

        with app.app_context():
            product = _publish(buyer, "Library Pass", "HALL_PASS", price="3.00")
            execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=1,
            )
            assert get_hall_pass_balance(buyer["seat_id"], buyer["class_id"]) >= 1


# ---------------------------------------------------------------------------
# Finding 20 — the lawful hall-pass path takes the PIN
# ---------------------------------------------------------------------------


class TestHallPassRequestRequiresThePin:
    """FEAT-IDEN-002 credential boundary: hall-pass use takes the PIN.

    Every test here first puts the seat in the state where the request would
    otherwise *succeed* — a pass in the balance and an active work session —
    so the only remaining reason to refuse is the credential.

    That setup is the whole point. A first draft asserted 403 against a bare
    seat, which the unfixed code also returned, because it had no pass to
    spend: the tests passed identically with and without the fix and proved
    nothing. A refusal is only evidence when refusing is the single thing left
    that can happen.
    """

    def _ready_to_leave(self, app, client, buyer, *, pin="4821", passphrase=None):
        """Give the seat a hall pass and an active session, then log in."""
        with app.app_context():
            product = _publish(buyer, f"Pass {buyer['seat_id']}", "HALL_PASS", price="1.00")
            execute_store_purchase(
                canonical_context=buyer["context"],
                policy_uuid=product.policy_uuid,
                quantity=1,
            )
            _set_credentials(buyer, pin=pin, passphrase=passphrase)

            from app.services.entitlement_service import get_hall_pass_balance
            assert get_hall_pass_balance(buyer["seat_id"], buyer["class_id"]) >= 1

        _login_student(client, buyer)
        # Clock in: a hall pass may only be requested from an active session.
        started = client.post("/api/tap", json={"action": "start_work", "pin": pin})
        assert started.status_code == 200, started.data

    def test_a_correct_pin_is_accepted(self, app, client, buyer):
        """The positive case, which is what makes the refusals meaningful."""
        self._ready_to_leave(app, client, buyer)

        response = client.post(
            "/api/hall-pass/request",
            json={"destination": "Library", "pin": "4821"},
        )

        assert response.status_code == 200, response.data

    def test_request_without_a_pin_is_refused(self, app, client, buyer):
        self._ready_to_leave(app, client, buyer)

        response = client.post("/api/hall-pass/request", json={"destination": "Library"})

        # The defect accepted this: no credential was checked at all, so anyone
        # holding the session could spend a pass off the seat's balance and put
        # the student on the attendance timeline as out of the room.
        assert response.status_code == 403, response.data

    def test_request_with_the_wrong_pin_is_refused(self, app, client, buyer):
        self._ready_to_leave(app, client, buyer)

        response = client.post(
            "/api/hall-pass/request",
            json={"destination": "Library", "pin": "0000"},
        )
        assert response.status_code == 403, response.data

    def test_the_passphrase_is_not_accepted_in_place_of_the_pin(self, app, client, buyer):
        """The matrix assigns one credential per action; near-misses must fail.

        Accepting either credential would satisfy the tests above while erasing
        the distinction the credential boundary exists to draw.
        """
        self._ready_to_leave(app, client, buyer, passphrase="correct-horse-battery")

        response = client.post(
            "/api/hall-pass/request",
            json={"destination": "Library", "pin": "correct-horse-battery"},
        )
        assert response.status_code == 403, response.data


# ---------------------------------------------------------------------------
# Finding 6A — teacher-entered dates are class-local, not UTC
# ---------------------------------------------------------------------------


class TestTeacherEnteredDatesResolveInTheClassTimezone:
    """A date picked in a form is the teacher's local date, not a UTC instant."""

    def test_class_local_midnight_is_not_utc_midnight_west_of_greenwich(self, app):
        """The arithmetic the fix depends on, stated independently of the route.

        For a US Pacific class, local midnight on the 2nd is 07:00 UTC on the
        2nd. Storing UTC midnight instead lands at 17:00 local on the *1st* —
        the previous local day — which is why payroll fired a day early.
        """
        with app.app_context():
            tz = pytz.timezone("America/Los_Angeles")
            chosen = date(2026, 10, 2)

            local_midnight_utc = tz.localize(datetime.combine(chosen, time.min)).astimezone(timezone.utc)
            naive_utc_midnight = datetime.combine(chosen, time.min, tzinfo=timezone.utc)

            assert local_midnight_utc != naive_utc_midnight
            assert local_midnight_utc > naive_utc_midnight
            # The old value falls on the previous day in the class's own timezone.
            assert naive_utc_midnight.astimezone(tz).date() == date(2026, 10, 1)
            assert local_midnight_utc.astimezone(tz).date() == chosen

    def test_payroll_settings_store_the_class_local_start_of_day(self, app, client, monkeypatch):
        """End-to-end: the stored anchor is local midnight for the class.

        Asserted through the route rather than the helper, because the defect
        was in how the route parsed the form — a helper-only test would have
        passed against the broken code.

        The class timezone is forced to one that matches neither UTC nor any
        plausible developer machine. Without that, this test is worthless on
        exactly the machines most likely to run it: the fixture classroom is
        ``America/Los_Angeles``, a naive datetime is interpreted by the driver
        as *host*-local, and on a Pacific laptop host-local and class-local
        coincide — so the broken code produced the right answer locally and the
        wrong one on the UTC server. The bug was invisible precisely where it
        would be looked for.
        """
        from tests.helpers import canonical_identities
        from tests.helpers.classroom_initializer import initialize_as_teacher
        from app.models import PayrollSettings

        forced_tz = "Asia/Tokyo"
        patched = dict(canonical_identities.CLASSROOMS["chemistry_p1"])
        patched["class_timezone"] = forced_tz
        monkeypatch.setitem(canonical_identities.CLASSROOMS, "chemistry_p1", patched)

        classroom = initialize_as_teacher("chemistry_p1", client, app)

        with app.app_context():
            class_row = ClassEconomy.query.filter_by(class_id=classroom.class_id).one()
            assert class_row.class_timezone == forced_tz, (
                "the class timezone override did not take effect, so this test "
                "would silently depend on the host's timezone"
            )

        response = client.post(
            "/admin/payroll/settings",
            data={
                "settings_mode": "simple",
                "simple_pay_rate": "0.50",
                "simple_frequency": "biweekly",
                "simple_first_pay_date": "2026-10-02",
            },
            follow_redirects=True,
        )
        assert response.status_code in (200, 302)

        with app.app_context():
            setting = (
                PayrollSettings.query
                .filter_by(class_id=classroom.class_id)
                .order_by(PayrollSettings.id.desc())
                .first()
            )
            assert setting is not None, "payroll settings did not persist"
            assert setting.first_pay_date is not None, (
                "first_pay_date did not persist; without it this test cannot "
                "distinguish a correct anchor from a missing one"
            )

            tz = pytz.timezone(forced_tz)
            stored = setting.first_pay_date
            if stored.tzinfo is None:
                stored = stored.replace(tzinfo=timezone.utc)

            # The date the teacher chose, read back in the class's own timezone.
            assert stored.astimezone(tz).date() == date(2026, 10, 2)
            assert stored.astimezone(tz).hour == 0

            # And explicitly not UTC midnight, which is the defect's signature.
            assert stored != datetime.combine(date(2026, 10, 2), time.min, tzinfo=timezone.utc)
