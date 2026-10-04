"""Teacher interval evidence stays scoped, complete, and pure on GET."""
from datetime import datetime, timedelta, timezone
from html import unescape
import re

import pytest

from app.extensions import db
from app.feats.prod import record_attendance_session
from app.models import AttendanceReasonCode, AttendanceSession, PayrollEvent, Transaction
from app.services.context_resolver import CanonicalContext
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.axe_wcag import wcag_live_server  # noqa: F401 -- pytest fixture injection


def _detail_url(client, public_id):
    roster = client.get('/admin/students').get_data(as_text=True)
    match = re.search(rf'href="(/admin/students/{re.escape(public_id)}\?nav=[^"]+)"', roster)
    assert match
    return unescape(match.group(1))


def _attendance(classroom, *, count=1, open_last=False):
    ctx = CanonicalContext(user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id, actor_role='teacher')
    seat_id = classroom.students[0].seat.id
    # Fixed closed work dates precede this feature's 2026-10-03 authority date.
    base = datetime(2026, 8, 1, 18, tzinfo=timezone.utc)
    pairs = []
    for index in range(count):
        start = base + timedelta(days=index)
        opening = record_attendance_session(ctx=ctx, target_seat_id=seat_id,
            status='active', mechanism='teacher', idempotency_key=f'detail:start:{seat_id}:{index}',
            reference_time_utc=start).session
        closing = None
        if not (open_last and index == count - 1):
            closing = record_attendance_session(ctx=ctx, target_seat_id=seat_id,
                status='inactive', mechanism='system', reason_code=AttendanceReasonCode.DONE_FOR_DAY,
                idempotency_key=f'detail:end:{seat_id}:{index}', reference_time_utc=start + timedelta(minutes=2)).session
        pairs.append((opening.id, closing.id if closing else None))
    return pairs


def test_complete_intervals_are_paired_before_pagination_and_get_is_pure(app, client, monkeypatch):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    pairs = _attendance(classroom, count=51)
    url = _detail_url(client, classroom.students[0].seat.public_id)
    before = (AttendanceSession.query.count(), PayrollEvent.query.count(), Transaction.query.count())

    def forbidden_write(*args, **kwargs):
        pytest.fail('Student attendance detail GET attempted a flush or commit')

    monkeypatch.setattr(db.session, 'flush', forbidden_write)
    monkeypatch.setattr(db.session, 'commit', forbidden_write)
    response = client.get(url)
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert len(re.findall(r'id="attendance-interval-\d+-\d+"', page)) == 50
    assert f'id="attendance-interval-{pairs[0][0]}-{pairs[0][1]}"' not in page
    assert '2m 0s' in page and 'System' in page and 'Done For Day' in page
    older = re.search(r'href="([^"]+)"[^>]*>Older intervals</a>', page)
    assert older
    older_url = unescape(older.group(1))
    next_response = client.get(older_url)
    assert next_response.status_code == 200
    older_page = next_response.get_data(as_text=True)
    assert len(re.findall(r'id="attendance-interval-\d+-\d+"', older_page)) == 1
    assert f'id="attendance-interval-{pairs[0][0]}-{pairs[0][1]}"' in older_page
    assert 'Newest intervals' in older_page
    assert before == (AttendanceSession.query.count(), PayrollEvent.query.count(), Transaction.query.count())
    # Cursor tampering cannot select arbitrary scope or history.
    tampered = re.sub(r'(attendance_cursor=)[^&#]+', r'\1invalid', older_url)
    assert client.get(tampered).status_code == 404
    other_url = _detail_url(client, classroom.students[1].seat.public_id)
    cursor = re.search(r'attendance_cursor=([^&#]+)', older_url).group(1)
    assert client.get(other_url + '&attendance_cursor=' + cursor).status_code == 404


def test_open_work_shows_source_without_creating_closure(app, client):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    pairs = _attendance(classroom, open_last=True)
    url = _detail_url(client, classroom.students[0].seat.public_id)
    before = AttendanceSession.query.count()
    html = client.get(url).get_data(as_text=True)
    assert 'Work without a recorded closing event' in html
    assert 'This interval has no recorded closing event.' in html
    assert 'Bounded at class day end' in html
    assert 'not a completed canonical pair' in html
    assert f'(#{pairs[0][0]})' in html
    assert 'id="attendance-interval-' not in html
    assert AttendanceSession.query.count() == before


@pytest.mark.parametrize('membership_status',['historical_unavailable','recorded'])
def test_historical_missing_contribution_is_explained_and_never_shown_as_zero(app, client, monkeypatch,membership_status):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    pair = _attendance(classroom)[0]
    url = _detail_url(client, classroom.students[0].seat.public_id)
    import app.services.payroll_interval_provenance as provenance
    monkeypatch.setattr(provenance, 'payroll_interval_memberships',
        lambda *args, **kwargs: {pair: {'status':membership_status,'event':None,'pricing':None,'requires_reconstruction':True}})
    html = client.get(url).get_data(as_text=True)
    attendance = html.split('<!-- ATTENDANCE TAB:')[1].split('<!-- RENT TAB')[0]
    assert 'Historical contribution unavailable' in attendance
    assert 'Review its source records before correcting this interval.' in attendance
    assert '$0.00' not in attendance
    assert 'Original payroll record' not in attendance
    assert 'Historical contributions are reconstructed from attendance, payroll windows' in html
    assert 'Invalidate' not in attendance


def test_detail_rejects_cross_class_navigation(app, client):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    url = _detail_url(client, classroom.students[0].seat.public_id)
    initialize_as_teacher('biology_block_a', client, app)
    assert client.get(url).status_code == 404


def test_rendered_interval_disclosures_work_by_keyboard_on_mobile(app, client, wcag_live_server):
    from tests.helpers.axe_wcag import authenticated_page, AXE_SOURCE, sync_playwright
    if sync_playwright is None:
        pytest.skip('Playwright is unavailable')
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    _attendance(classroom, count=2, open_last=True)
    url = _detail_url(client, classroom.students[0].seat.public_id) + '&tab=attendance'
    with client.session_transaction() as session:
        session_data = dict(session)
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:
            pytest.skip(f'Chromium is unavailable: {exc}')
        with browser:
            page = authenticated_page(browser, wcag_live_server, session_data)
            page.set_viewport_size({'width': 390, 'height': 844})
            response = page.goto(wcag_live_server + url, wait_until='networkidle')
            assert response and response.ok
            assert page.locator('#attendance').is_visible()
            disclosure = page.locator('#attendance details[id^="attendance-interval-"]').first
            summary = disclosure.locator('summary')
            summary.focus()
            page.keyboard.press('Enter')
            assert disclosure.evaluate('(element) => element.open')
            assert disclosure.locator('caption').inner_text() == 'Original attendance records'
            page.keyboard.press('Space')
            assert not disclosure.evaluate('(element) => element.open')
            summary.click()
            assert disclosure.evaluate('(element) => element.open')
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            page.add_script_tag(content=AXE_SOURCE)
            violations = page.evaluate("""async () => (await axe.run(document.getElementById('attendance'), {
                runOnly: {type:'tag', values:['wcag2a','wcag2aa']}
            })).violations""")
            assert not violations, violations
            page.context.close()


def test_payroll_history_evidence_notice_does_not_require_an_attendance_pair(app, client, monkeypatch):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    url = _detail_url(client, classroom.students[0].seat.public_id)
    import app.services.payroll_interval_provenance as provenance
    monkeypatch.setattr(provenance, 'payroll_provenance_history_limitations', lambda *args, **kwargs: True)
    html = client.get(url).get_data(as_text=True)
    assert 'Historical contributions are reconstructed from attendance, payroll windows' in html
    assert 'No attendance records found for this student.' in html


def test_new_settlement_detail_shows_pending_then_verified_posted_contribution(app, client):
    from app.feats.prod import record_payroll_event
    from app.utils.audit_verifier import verify_record_creation_lineage
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    _attendance(classroom)
    seat_id = classroom.students[0].seat.id
    ctx = CanonicalContext(user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id, actor_role='teacher')
    from app.feats.base import FEATContext
    from app.services.ledger_settlement_service import settle_balances
    from tests.helpers.ledger import record_ledger_fixture
    with FEATContext("FEAT-LED-001", idempotency_key="detail:cursor:seed"):
        record_ledger_fixture(seat_id=seat_id, class_id=classroom.class_id,
            amount=0, posted=True)
    result = record_payroll_event(ctx=ctx, target_seat_id=seat_id, payroll_event_type='payroll',
        correlation_id='corr_detail:v1:credit', idempotency_key='detail:v1:credit', mechanism='TEACHER',
        reference_time_utc=datetime(2026, 8, 2, 18, tzinfo=timezone.utc))
    event = result.payroll_event
    assert event.summary_json['allocation_version'] == 1
    assert verify_record_creation_lineage('payroll_event', event, classroom.class_id)
    url = _detail_url(client, classroom.students[0].seat.public_id)
    response = client.get(url)
    assert response.status_code == 200
    attendance = response.get_data(as_text=True).split('<!-- ATTENDANCE TAB:')[1].split('<!-- RENT TAB')[0]
    assert 'Payroll recorded · Pending posting' in attendance
    assert '$0.00' not in attendance
    assert f'Payroll #{event.id}' in attendance
    credit = Transaction.query.filter_by(class_id=classroom.class_id,
        idempotency_key='detail:v1:credit').one()
    frozen_lineage = (credit.lineage_event_id, credit.lineage_token, credit.lineage_version)
    with app.app_context(), FEATContext("FEAT-LED-003", idempotency_key="detail:v1:reconcile"):
        settle_balances(seat_id, classroom.class_id)
    response = client.get(url)
    assert response.status_code == 200
    attendance = response.get_data(as_text=True).split('<!-- ATTENDANCE TAB:')[1].split('<!-- RENT TAB')[0]
    assert 'Historically settled' in attendance
    assert f'${credit.amount:.2f}' in attendance
    assert 'Contribution unavailable' not in attendance
    assert 'Pending posting' not in attendance
    assert frozen_lineage == (credit.lineage_event_id, credit.lineage_token, credit.lineage_version)
    assert verify_record_creation_lineage('ledger_transaction', credit, classroom.class_id)


def test_unknown_historical_work_discloses_incomplete_estimate(app, client):
    import sqlalchemy as sa
    from app.models import PayrollSettings
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    _attendance(classroom)
    cid, actor, target = classroom.class_id, classroom.teacher_seat.id, classroom.students[0].seat.id
    public_id = classroom.students[0].seat.public_id
    policy_uuid = PayrollSettings.query.filter_by(class_id=cid).first().policy_uuid
    # Simulate a retained pre-rollout business row on the disposable database.
    # The current forward-only migration cannot be downgraded. Suspend only
    # its creation gate while seeding the old NULL lineage, then restore it in
    # the same transaction; runtime guards and historical evidence stay intact.
    db.session.rollback()
    with db.engine.begin() as connection:
        connection.execute(sa.text('ALTER TABLE payroll_event DISABLE TRIGGER payroll_event_creation_lineage_required'))
        connection.execute(sa.text('''INSERT INTO payroll_event
            (class_id, actor_seat_id, target_seat_id, correlation_id, idempotency_key,
             mechanism, payroll_event_type, recorded_at, policy_uuid, summary_json)
            VALUES (:cid, :actor, :target, 'detail-historical', 'detail-historical',
                'TEACHER', 'payroll', :recorded_at, :policy, CAST(:summary AS json))'''),
            {'cid': cid, 'actor': actor, 'target': target, 'policy': policy_uuid,
             'recorded_at': datetime(2026, 8, 1, 18, 1, tzinfo=timezone.utc),
             'summary': '{"settlement_rule":"legacy_open"}'})
        connection.execute(sa.text('ALTER TABLE payroll_event ENABLE TRIGGER payroll_event_creation_lineage_required'))
    url = _detail_url(client, public_id)
    response = client.get(url)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Unpaid earnings estimates exclude that work and are incomplete.' in html
    assert 'Payroll settlement is blocked until the evidence can be resolved.' in html
    assert 'Historical contribution unavailable' in html


@pytest.mark.parametrize('membership_status',['historical_unavailable','recorded'])
def test_validated_historical_detail_exposes_contribution_originals_and_teacher_control(app,client,monkeypatch,membership_status):
    from types import SimpleNamespace
    classroom=initialize_as_teacher('chemistry_p1',client,app)
    pair=_attendance(classroom)[0]
    url=_detail_url(client,classroom.students[0].seat.public_id)
    import app.services.payroll_interval_provenance as provenance
    import app.feats.attendance_interval_invalidation_feat as feat
    monkeypatch.setattr(provenance,'payroll_interval_memberships',lambda *a,**k:{pair:{
        'status':membership_status,'event':SimpleNamespace(id=103) if membership_status=='recorded' else None,
        'pricing':None,'requires_reconstruction':True}})
    at=datetime(2026,8,3,18,tzinfo=timezone.utc)
    monkeypatch.setattr(feat,'historical_attendance_interval_details',lambda **k:{pair:{
        'allocated_cents':125,'status':'verified','allocation_version':'historical-reconstruction-v1',
        'original_events':(SimpleNamespace(event_id=101,recorded_at=at),SimpleNamespace(event_id=102,recorded_at=at)),}})
    counts=tuple(model.query.count() for model in (AttendanceSession,PayrollEvent,Transaction))
    response=client.get(url)
    assert response.status_code==200
    html=response.get_data(as_text=True)
    attendance=html.split('<!-- ATTENDANCE TAB:')[1].split('<!-- RENT TAB')[0]
    assert '$1.25' in attendance and 'Paid' in attendance
    assert 'Payroll #101' in attendance and 'Payroll #102' in attendance
    assert 'Invalidate work interval' in attendance and 'data-attendance-correction' in attendance
    assert counts==tuple(model.query.count() for model in (AttendanceSession,PayrollEvent,Transaction))


def test_unclosed_projection_distinguishes_observation_from_day_boundary(app):
    from app.services.attendance_service import list_attendance_intervals
    classroom = initialize_as_teacher('chemistry_p1', app.test_client(), app)
    pairs = _attendance(classroom, open_last=True)
    opening = db.session.get(AttendanceSession, pairs[0][0])
    ctx = CanonicalContext(user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id, actor_role='teacher')
    observed = list_attendance_intervals(classroom.students[0].seat.id, classroom.class_id,
        ctx=ctx, as_of_utc=opening.timestamp + timedelta(seconds=30))[0]
    bounded = list_attendance_intervals(classroom.students[0].seat.id, classroom.class_id,
        ctx=ctx, as_of_utc=opening.timestamp + timedelta(days=2))[0]
    assert observed.closing_event_id is None and not observed.bounded_at_day_end
    assert bounded.closing_event_id is None and bounded.bounded_at_day_end
    assert AttendanceSession.query.count() == 1
