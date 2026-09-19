"""Per-ticket disclosure grants are independent and enforced before rendering."""
from copy import deepcopy
from types import SimpleNamespace
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from bs4 import BeautifulSoup

from app import db
from app.models import Issue
from app.routes.system_admin import _issue_to_view, _correlation_pack_to_view
from app.services.support_disclosure import disclosed_snapshot, permissions_from_form
from app.utils.opaque_refs import make_opaque_ref
from tests.dom.support.test_escalation_disclosure_and_scope import _submit_issue
from tests.helpers.canonical_classroom import login_teacher
from tests.helpers.support_domain import initialize_support_student, initialize_support_teacher


@pytest.mark.parametrize('permission', [None, 'balances', 'transaction', 'recent_transactions'])
def test_individual_permissions_never_grant_other_categories(permission):
    snapshot = {
        'timestamp': 'now', 'ip_address': '192.0.2.1', 'user_agent': 'Test browser',
        'page_url': '/student/banking', 'balances': {'checking': 17, 'private': 'hidden'},
        'transaction': {'amount': 9, 'seat_id': 99},
        'recent_transactions': [{'amount': 2, 'private': 'hidden'}],
        'attendance': 'unapproved future category', 'notes': 'never attach roster notes',
    }
    before = deepcopy(snapshot)
    permissions = {permission: True} if permission else {'all': True}
    result = disclosed_snapshot(SimpleNamespace(context_snapshot=snapshot, support_permissions=permissions))
    assert result['ip_address'] == '192.0.2.1' and result['page_url'] == '/student/banking'
    for category in ('balances', 'transaction', 'recent_transactions'):
        assert (category in result) == (category == permission)
    assert 'attendance' not in result and 'notes' not in result
    assert 'private' not in str(result) and 'seat_id' not in str(result)
    assert snapshot == before


def test_only_explicit_individual_checkbox_values_are_accepted():
    permissions = permissions_from_form({'share_all': 'on', 'share_balances': 'true', 'share_transaction': 'on'})
    assert permissions == dict(balances=False, transaction=True, recent_transactions=False, student_report=False)
    assert disclosed_snapshot(SimpleNamespace(context_snapshot={'balances': {}}, support_permissions={'balances': 'true'})) == {}


@pytest.mark.parametrize('selected', [None, 'balances', 'student_report'])
def test_teacher_escalation_persists_only_selected_permissions(client, selected):
    classroom, student = initialize_support_student('chemistry_p1', client, client.application)
    issue = _submit_issue(classroom, student, explanation='PRIVATE STUDENT REPORT')
    assert issue.correlation_pack is not None
    pack_before = deepcopy(_correlation_pack_to_view(issue.correlation_pack))
    snapshot_before = deepcopy(issue.context_snapshot)
    login_teacher(client, classroom)
    data = {'escalation_reason': 'System Error', 'share_all': 'on'}
    if selected:
        data[f'share_{selected}'] = 'on'
    response = client.post(f"/admin/issues/{make_opaque_ref('issue', issue.id)}/escalate", data=data)
    assert response.status_code == 302
    db.session.refresh(issue)
    assert issue.status == Issue.STATUS_ESCALATED_TO_DEV
    view = _issue_to_view(issue)
    assert ('balances' in view['context_snapshot']) == (selected == 'balances')
    assert (view['student_explanation'] == 'PRIVATE STUDENT REPORT') == (selected == 'student_report')
    assert 'recent_transactions' not in view['context_snapshot']
    assert view['class_label'] is None
    assert _correlation_pack_to_view(issue.correlation_pack) == pack_before
    assert issue.context_snapshot == snapshot_before


def test_foreign_teacher_cannot_grant_disclosure(client):
    classroom, student = initialize_support_student('chemistry_p1', client, client.application)
    issue = _submit_issue(classroom, student)
    issue_id = issue.id
    initialize_support_teacher('biology_block_a', client, client.application)
    response = client.post(f"/admin/issues/{make_opaque_ref('issue', issue_id)}/escalate", data={
        'escalation_reason': 'System Error', 'share_balances': 'on',
    })
    assert response.status_code == 404
    db.session.refresh(issue)
    assert issue.support_permissions == {} and issue.status == Issue.STATUS_OPEN


def test_teacher_form_has_separate_unchecked_labeled_permissions(client):
    classroom, student = initialize_support_student('chemistry_p1', client, client.application)
    issue = _submit_issue(classroom, student)
    login_teacher(client, classroom)
    response = client.get(f"/admin/issues/{make_opaque_ref('issue', issue.id)}")
    assert response.status_code == 200
    from tests.test_accessibility import _audit_html_accessibility
    _audit_html_accessibility(response.text)
    soup = BeautifulSoup(response.text, 'html.parser')
    for field in ('balances', 'transaction', 'recent_transactions', 'student_report', 'class_name'):
        checkbox = soup.select_one(f'input[name="share_{field}"]')
        assert checkbox and not checkbox.has_attr('checked')
        assert soup.find('label', attrs={'for': checkbox['id']})
    assert not soup.select('input[name="share_all"]')


def test_alternate_operator_detail_cannot_bypass_report_permission(client):
    from tests.dom.interpretation.helpers import create_sysadmin, login_sysadmin
    classroom, student = initialize_support_student('chemistry_p1', client, client.application)
    issue = _submit_issue(classroom, student, explanation='WITHHELD REPORT CONTENT')
    sysadmin = create_sysadmin(username='disclosure_operator')
    login_sysadmin(client, 'disclosure_operator', sysadmin.id)
    response = client.get(f"/sysadmin/user-reports/{make_opaque_ref('report', issue.id)}")
    assert response.status_code == 200
    assert 'WITHHELD REPORT CONTENT' not in response.text


def test_permission_migration_defaults_old_rows_to_no_consent(monkeypatch):
    path = Path(__file__).resolve().parents[3] / 'migrations/versions/d2b2c3d4e5f6_support_disclosure_permissions.py'
    spec = importlib.util.spec_from_file_location('support_permissions_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    with sa.create_engine('sqlite://').begin() as conn:
        conn.execute(sa.text('CREATE TABLE issues (id INTEGER PRIMARY KEY)'))
        conn.execute(sa.text('INSERT INTO issues VALUES (1)'))
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(conn)))
        migration.upgrade()
        migration.upgrade()
        assert conn.execute(sa.text('SELECT support_permissions FROM issues')).scalar_one() == '{}'
        migration.downgrade()
        migration.downgrade()
        assert [c['name'] for c in sa.inspect(conn).get_columns('issues')] == ['id']


@pytest.mark.parametrize('grant', [False, True])
def test_operator_page_renders_balances_only_after_teacher_selection(client, monkeypatch, grant):
    from decimal import Decimal
    from app.utils import issue_helpers
    from tests.dom.interpretation.helpers import create_sysadmin, login_sysadmin
    from tests.test_accessibility import _audit_html_accessibility
    monkeypatch.setattr(issue_helpers, 'get_available_balances', lambda *_: (Decimal('1234567.89'), Decimal('0')))
    classroom, student = initialize_support_student('chemistry_p1', client, client.application)
    issue = _submit_issue(classroom, student)
    login_teacher(client, classroom)
    form = {'escalation_reason': 'System Error'}
    if grant:
        form['share_balances'] = 'on'
    assert client.post(f"/admin/issues/{make_opaque_ref('issue', issue.id)}/escalate", data=form).status_code == 302
    admin = create_sysadmin(username='rendered_operator')
    login_sysadmin(client, 'rendered_operator', admin.id)
    response = client.get(f"/sysadmin/issues/{make_opaque_ref('issue', issue.id)}")
    assert response.status_code == 200
    assert ('1234567.89' in response.text) == grant
    assert 'Correlation Pack' in response.text
    assert 'IP address' in response.text and 'Browser details' in response.text
    _audit_html_accessibility(response.text)


def test_direct_teacher_submission_class_name_is_separate_permission(client):
    from tests.helpers.support_domain import seed_support_issue_categories
    classroom = initialize_support_teacher('chemistry_p1', client, client.application)
    seed_support_issue_categories()
    response = client.post('/admin/help-support', data={
        'issue_category': 'bug', 'title': 'Consent test', 'description': 'TEACHER REPORT',
        'share_class_name': 'on',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert 'TEACHER REPORT' in response.text  # The ticket stays in My Tickets.
    issue = Issue.query.filter_by(title='Consent test').one()
    view = _issue_to_view(issue)
    assert view['class_label'] == classroom.economy.display_name
    assert view['student_explanation'] == 'TEACHER REPORT'
    assert 'balances' not in view['context_snapshot']
    assert issue.class_public_id == classroom.economy.class_public_id


def test_persisted_pack_keeps_route_diagnostics_without_class_data_permission(client):
    classroom, student = initialize_support_student('chemistry_p1', client, client.application)
    response = client.get('/student/help-support/submit-issue')
    assert response.status_code == 200
    # The independent after-request writer is disabled by the test configuration.
    # Exercise its production persistence service in the fixture transaction.
    from app.services.tlcp import persist_request_trace
    from app.feats.base import FEATContext
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='support:trace'):
        persist_request_trace({
            'actor_type': 'student', 'actor_public_id': student.seat.public_id,
            'class_id': classroom.class_id, 'method': 'GET',
            'endpoint': 'student.submit_general_issue',
        }, response.headers.get('X-Request-Id'), 200)
    issue = _submit_issue(classroom, student)
    db.session.expire_all()
    pack = _correlation_pack_to_view(issue.correlation_pack)
    assert pack is not None
    assert any(row['endpoint'] == 'student.submit_general_issue' for row in pack['request_trace_json'])
    assert all(row['request_id'] and row['method'] for row in pack['request_trace_json'])
    assert 'balances' not in _issue_to_view(issue)['context_snapshot']


def test_snapshot_is_frozen_and_seat_deletion_removes_support_rows(client, monkeypatch):
    from app.feats.base import FEATContext
    from app.models import TicketCorrelationPack, IssueStatusHistory, Seat
    from app.services.classroom_setup import delete_seat_with_profile
    from app.services.issue_service import attach_correlation_pack
    from app.utils import issue_helpers
    classroom, student = initialize_support_student('chemistry_p1', client, client.application)
    issue = _submit_issue(classroom, student)
    issue_id = issue.id
    saved = deepcopy(issue.context_snapshot)
    pack_saved = deepcopy(_correlation_pack_to_view(issue.correlation_pack))
    with FEATContext('FEAT-SUP-001', idempotency_key='support:grant'):
        issue.support_permissions = {'balances': True}
    with FEATContext('FEAT-IDEN-006', idempotency_key='support:rename-source'):
        student.profile.first_name = 'Changed After Submission'
    def no_live_balance_read(*args, **kwargs):
        pytest.fail('Support disclosure must not re-read class balances')
    monkeypatch.setattr(issue_helpers, 'get_available_balances', no_live_balance_read)
    assert _issue_to_view(issue)['context_snapshot']['balances'] == saved['balances']
    assert issue.context_snapshot == saved
    assert _correlation_pack_to_view(issue.correlation_pack) == pack_saved
    with pytest.raises(ValueError, match='cannot be replaced'):
        attach_correlation_pack(issue, actor_type='student', actor_public_id=student.seat.public_id, class_id=classroom.class_id)
    with FEATContext('FEAT-IDEN-007', idempotency_key='support:delete-seat'):
        delete_seat_with_profile(student.seat)
        db.session.flush()
    db.session.expire_all()
    assert db.session.get(Issue, issue_id) is None
    assert db.session.get(TicketCorrelationPack, issue_id) is None
    assert IssueStatusHistory.query.filter_by(issue_id=issue_id).count() == 0


def test_teacher_account_deletion_removes_seat_scoped_ticket_and_pack(client):
    from tests.helpers.support_domain import seed_support_issue_categories
    from tests.dom.identity.helpers import admin_delete_class, valid_destruction_gate
    from app.models import TicketCorrelationPack, User
    classroom = initialize_support_teacher('chemistry_p1', client, client.application)
    seed_support_issue_categories()
    teacher_id = classroom.teacher_user.id
    response = client.post('/admin/help-support', data={
        'class_id': 'account', 'issue_category': 'bug', 'title': 'Teacher ticket',
        'description': 'Teacher context',
    })
    assert response.status_code == 302
    issue = Issue.query.filter_by(title='Teacher ticket').one()
    issue_id = issue.id
    assert issue.class_public_id == classroom.economy.class_public_id
    assert issue.actor_public_id == classroom.teacher_seat.public_id
    assert issue.correlation_pack is not None
    phrase = f'DELETE {classroom.economy.display_name}'.upper()
    response = admin_delete_class(client, **valid_destruction_gate(phrase))
    assert response.status_code == 200 and response.json.get('account_deleted') is True
    db.session.expire_all()
    assert db.session.get(User, teacher_id) is None
    assert db.session.get(Issue, issue_id) is None
    assert db.session.get(TicketCorrelationPack, issue_id) is None


def test_support_seat_revision_scopes_the_ticket_without_a_key_to_seats(monkeypatch):
    """`class_public_id` becomes required; `actor_public_id` gains no foreign key.

    This revision used to create `fk_issues_actor_public_id_seats` and cascade a
    ticket away with its seat. INV-ARC-021 §V.7 permits a cross-domain key only
    to `class_id`, `seat_id` or `user_id`, so `d9e1f3a5b7c9` removes it, and
    building it here only to drop it a few revisions later was both
    contradictory and unsafe: nothing reconciled `issues` first, so one ticket
    pointing at a seat that no longer exists failed the upgrade outright.

    Ticket lifetime is enforced by the explicit sweep in
    `app/utils/student_deletion.py` (DOM-SUP-001 §X), which is also what allows
    an unclaimed seat to keep an earlier claimant's tickets — a state a cascade
    cannot express.
    """
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).resolve().parents[3] / 'migrations/versions/e3c3d4e5f6a7_support_seat_deletion_cascade.py'
    spec = importlib.util.spec_from_file_location('support_seat_cascade', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with sa.create_engine('sqlite://').begin() as conn:
        conn.execute(sa.text('PRAGMA foreign_keys = ON'))
        conn.execute(sa.text('CREATE TABLE seats (public_id VARCHAR(36) PRIMARY KEY)'))
        conn.execute(sa.text('CREATE TABLE issues (id INTEGER PRIMARY KEY, actor_public_id VARCHAR(64), class_public_id VARCHAR(36))'))
        conn.execute(sa.text("INSERT INTO seats VALUES ('seat-reference')"))
        conn.execute(sa.text("INSERT INTO issues VALUES (1, 'seat-reference', 'class-reference')"))
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(conn)))
        migration.upgrade()
        migration.upgrade()  # idempotent
        columns = {c['name']: c for c in sa.inspect(conn).get_columns('issues')}
        assert columns['class_public_id']['nullable'] is False
        assert sa.inspect(conn).get_foreign_keys('issues') == []

        # The ticket outlives its seat here; the deletion path removes it.
        conn.execute(sa.text("DELETE FROM seats WHERE public_id = 'seat-reference'"))
        assert conn.execute(sa.text('SELECT count(*) FROM issues')).scalar_one() == 1

        migration.downgrade()
        migration.downgrade()  # idempotent
        assert sa.inspect(conn).get_foreign_keys('issues') == []
        columns = {c['name']: c for c in sa.inspect(conn).get_columns('issues')}
        assert columns['class_public_id']['nullable'] is True


def test_teacher_ticket_keeps_original_class_label_after_class_rename(client):
    from app.feats.base import FEATContext
    from tests.helpers.support_domain import seed_support_issue_categories
    classroom = initialize_support_teacher('chemistry_p1', client, client.application)
    seed_support_issue_categories()
    original_label = classroom.economy.display_name
    response = client.post('/admin/help-support', data={
        'issue_category': 'bug', 'title': 'Frozen context', 'description': 'Frozen teacher report',
        'class_id': 'account',  # Untrusted input cannot remove canonical class scope.
    })
    assert response.status_code == 302
    issue = Issue.query.filter_by(title='Frozen context').one()
    assert issue.class_public_id == classroom.economy.class_public_id
    saved = deepcopy(issue.context_snapshot)
    with FEATContext('FEAT-CLASS-002', idempotency_key='support:rename-class'):
        classroom.economy.display_name = 'Changed after ticket submission'
    response = client.get('/admin/help-support')
    assert response.status_code == 200
    assert original_label in response.text
    assert issue.class_label == original_label and issue.context_snapshot == saved
