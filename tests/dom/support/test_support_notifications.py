"""DOM-SUP-001 §XI: commit ordering, disclosure and delivery isolation."""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from flask import Flask
from sqlalchemy import event, select

from app.extensions import db
from app.feats.base import FEATContext
from app.models import Issue
from app.services import support_notifications as notifications
from app.utils.opaque_refs import make_opaque_ref, resolve_opaque_ref
from tests.helpers.canonical_classroom import login_teacher
from tests.helpers.support_domain import (
    initialize_support_student,
    initialize_support_teacher,
    seed_support_issue_categories,
    submit_support_ticket,
)
from tests.dom.support.test_escalation_disclosure_and_scope import _submit_issue


@pytest.fixture
def delivery_app():
    app = Flask(__name__)
    app.config.update(SUPPORT_IFTTT_EVENT="cth_support_issue", SUPPORT_IFTTT_KEY="secret-test-key")
    with app.app_context():
        yield app


@pytest.fixture
def webhook(monkeypatch):
    calls = []

    class Connection:
        def __init__(self, host, timeout):
            assert host == "maker.ifttt.com"
            assert timeout == 3

        def request(self, method, path, body, headers):
            assert method == "POST"
            assert path == "/trigger/cth_support_issue/with/key/secret-test-key"
            assert headers == {"Content-Type": "application/json"}
            calls.append(json.loads(body))

        def getresponse(self):
            return SimpleNamespace(status=200)

        def close(self):
            pass

    monkeypatch.setattr(notifications.http.client, "HTTPSConnection", Connection)
    return calls


def _enable(app, monkeypatch):
    monkeypatch.setitem(app.config, "SUPPORT_IFTTT_EVENT", "cth_support_issue")
    monkeypatch.setitem(app.config, "SUPPORT_IFTTT_KEY", "secret-test-key")


def test_teacher_filing_sends_only_allowlisted_values_after_durable_commit(client, monkeypatch, webhook):
    classroom = initialize_support_teacher("chemistry_p1", client, client.application)
    seed_support_issue_categories()
    _enable(client.application, monkeypatch)
    original_delivery = notifications._deliver

    def verify_commit(payload):
        issue_id = resolve_opaque_ref("issue", payload["value2"])
        # A separate connection proves the issue is visible after the commit.
        with db.engine.connect() as connection:
            assert connection.execute(select(Issue.id).where(Issue.id == issue_id)).scalar_one() == issue_id
        original_delivery(payload)

    monkeypatch.setattr(notifications, "_deliver", verify_commit)
    response = submit_support_ticket(
        client, issue_category="general", title="Private name in title",
        description="Private student detail", expected_behavior="Private expected result",
        page_url="/private?student=identifying",
    )
    assert response.status_code == 200
    assert b"submitted directly" in response.data
    assert len(webhook) == 1
    payload = webhook[0]
    assert set(payload) == {"value1", "value2", "value3"}
    assert payload["value1"] == "New teacher support ticket"
    assert datetime.fromisoformat(payload["value3"]).utcoffset().total_seconds() == 0
    issue = db.session.get(Issue, resolve_opaque_ref("issue", payload["value2"]))
    assert issue.actor_public_id == classroom.teacher_seat.public_id
    assert "Private" not in json.dumps(payload)
    assert str(classroom.teacher_seat.public_id) not in json.dumps(payload)
    # Reading the dashboard cannot re-send the notification.
    client.get("/admin/help-support")
    assert len(webhook) == 1
    # Escalating an already filed teacher ticket is not a new student escalation.
    client.post(
        f"/admin/issues/{make_opaque_ref('issue', issue.id)}/escalate",
        data={"escalation_reason": "Teacher follow-up"},
    )
    assert len(webhook) == 1


def test_student_filing_is_silent_escalation_notifies_once(client, monkeypatch, webhook):
    classroom, student = initialize_support_student("chemistry_p1", client, client.application)
    _enable(client.application, monkeypatch)
    issue = _submit_issue(classroom, student, explanation="Private student report")
    issue_id = issue.id
    assert webhook == []
    login_teacher(client, classroom)
    path = f"/admin/issues/{make_opaque_ref('issue', issue_id)}/escalate"
    response = client.post(path, data={"escalation_reason": "Private reason", "share_class_name": "on"})
    assert response.status_code == 302
    assert len(webhook) == 1
    assert webhook[0]["value1"] == "Student support ticket escalated by teacher"
    assert resolve_opaque_ref("issue", webhook[0]["value2"]) == issue_id
    assert "Private" not in json.dumps(webhook[0])
    assert db.session.get(Issue, issue_id).status == Issue.STATUS_ESCALATED_TO_DEV
    client.post(path, data={"escalation_reason": "Repeat"})
    assert len(webhook) == 1


def test_refused_escalation_does_not_notify(client, monkeypatch, webhook):
    classroom, student = initialize_support_student("chemistry_p1", client, client.application)
    issue = _submit_issue(classroom, student)
    login_teacher(client, classroom)
    _enable(client.application, monkeypatch)
    response = client.post(f"/admin/issues/{make_opaque_ref('issue', issue.id)}/escalate", data={})
    assert response.status_code == 302
    assert webhook == []
    assert issue.status == Issue.STATUS_OPEN


def test_failed_commit_discards_notification_and_ticket(client, monkeypatch, webhook):
    initialize_support_teacher("chemistry_p1", client, client.application)
    seed_support_issue_categories()
    _enable(client.application, monkeypatch)

    def fail_commit(session):
        if session.info.get(notifications._PENDING):
            from sqlalchemy.exc import SQLAlchemyError
            raise SQLAlchemyError("Synthetic commit failure")

    event.listen(db.session, "before_commit", fail_commit)
    try:
        response = submit_support_ticket(client, issue_category="general", title="Failed filing", description="No commit")
    finally:
        event.remove(db.session, "before_commit", fail_commit)
    assert response.status_code == 200
    assert webhook == []
    assert Issue.query.filter_by(title="Failed filing").count() == 0
    assert notifications._PENDING not in db.session.info


def test_savepoint_release_waits_for_outer_commit_and_rollback_drops_only_its_values(app, monkeypatch, webhook):
    _enable(app, monkeypatch)
    with FEATContext("FEAT-SUP-001", idempotency_key="test:sup:savepoint"):
        with db.session.begin_nested():
            notifications.schedule_support_notification(101, event_type="teacher_ticket")
        assert webhook == []
        with pytest.raises(ValueError):
            with db.session.begin_nested():
                notifications.schedule_support_notification(102, event_type="teacher_ticket")
                raise ValueError("Rollback savepoint")
        assert webhook == []
    assert len(webhook) == 1
    assert resolve_opaque_ref("issue", webhook[0]["value2"]) == 101


def test_outer_rollback_cannot_leak_notification_into_later_commit(app, monkeypatch, webhook):
    _enable(app, monkeypatch)
    with pytest.raises(ValueError):
        with FEATContext("FEAT-SUP-001", idempotency_key="test:sup:rollback"):
            notifications.schedule_support_notification(101, event_type="teacher_ticket")
            raise ValueError("Rollback")
    with FEATContext("FEAT-SUP-001", idempotency_key="test:sup:later"):
        pass
    assert webhook == []


def test_closed_session_cannot_leak_notification_into_later_commit(app, monkeypatch, webhook):
    _enable(app, monkeypatch)
    with db.session.begin():
        notifications.schedule_support_notification(101, event_type="teacher_ticket")
        db.session.close()
    with FEATContext("FEAT-SUP-001", idempotency_key="test:sup:after-close"):
        pass
    assert webhook == []


def test_delivery_failure_keeps_teacher_filing_successful(client, monkeypatch, caplog):
    initialize_support_teacher("chemistry_p1", client, client.application)
    seed_support_issue_categories()
    _enable(client.application, monkeypatch)

    def fail_connection(*args, **kwargs):
        raise TimeoutError("secret-test-key Private text")

    monkeypatch.setattr(notifications.http.client, "HTTPSConnection", fail_connection)
    response = submit_support_ticket(client, issue_category="general", title="Committed filing", description="Private detail")
    assert response.status_code == 200
    assert b"submitted directly" in response.data
    assert Issue.query.filter_by(title="Committed filing").count() == 1
    alert_logs = [r.message for r in caplog.records if r.message.startswith("support_notification_")]
    assert alert_logs == ["support_notification_delivery_failed reason=transport"]


@pytest.mark.parametrize("status", [204, 302, 400, 503])
def test_http_status_is_bounded_and_never_redirected(delivery_app, monkeypatch, caplog, status):
    connections = []

    class Connection:
        def __init__(self, *args, **kwargs):
            connections.append(self)

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return SimpleNamespace(status=status)

        def close(self):
            pass

    monkeypatch.setattr(notifications.http.client, "HTTPSConnection", Connection)
    caplog.set_level("INFO")
    notifications._deliver({"value1": "label", "value2": "ref", "value3": "time"})
    assert len(connections) == 1
    if status == 204:
        assert "support_notification_delivered" in caplog.text
    else:
        assert f"reason=http_status status={status}" in caplog.text
    assert "secret-test-key" not in caplog.text


@pytest.mark.parametrize("event_name,key", [("", "key"), ("event", ""), ("bad/event", "key")])
def test_invalid_configuration_never_opens_connection(delivery_app, monkeypatch, webhook, caplog, event_name, key):
    delivery_app.config.update(SUPPORT_IFTTT_EVENT=event_name, SUPPORT_IFTTT_KEY=key)
    notifications._deliver({})
    assert webhook == []
    assert "reason=configuration" in caplog.text


def test_unconfigured_integration_schedules_nothing(delivery_app):
    delivery_app.config.update(SUPPORT_IFTTT_EVENT="", SUPPORT_IFTTT_KEY="")
    # Even outside a transaction, disabled integration requires no DB access.
    notifications.schedule_support_notification(101, event_type="teacher_ticket")
