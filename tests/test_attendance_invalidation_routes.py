"""Signed teacher navigation and correction request boundaries."""
from urllib.parse import urlsplit,parse_qs
from app.models import AttendanceIntervalInvalidation
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.test_student_detail_attendance_intervals import _attendance,_detail_url


def _url(client,classroom):
    target=classroom.students[0].seat
    nav=parse_qs(urlsplit(_detail_url(client,target.public_id)).query)['nav'][0]
    return f'/admin/students/{target.public_id}/attendance/invalidation?nav={nav}'


def test_preview_and_confirm_routes_preserve_scope_and_original_scans(app,client):
    classroom=initialize_as_teacher('chemistry_p1',client,app)
    pairs=_attendance(classroom)
    url=_url(client,classroom)
    request={'opening_event_id':pairs[0][0],'closing_event_id':pairs[0][1],'reason_code':'INVALID_ATTENDANCE'}
    result=client.get(url+'&opening_event_id='+str(request['opening_event_id'])+'&closing_event_id='+str(request['closing_event_id'])+'&reason_code='+request['reason_code'])
    assert result.status_code==200,result.data
    p=result.json
    assert AttendanceIntervalInvalidation.query.count()==0
    response=client.post(url,json=dict(request,idempotency_key='route:invalidation:1',expected_preview_identity=p['expected_preview_identity']))
    assert response.status_code==200,response.data
    assert response.json['status']=='accepted'
    assert client.post(url,json=dict(request,idempotency_key='route:invalidation:1',expected_preview_identity=p['expected_preview_identity'])).json['replayed']
    html=client.get(_detail_url(client,classroom.students[0].seat.public_id)).get_data(as_text=True)
    assert 'Ineligible · Invalidated' in html


def test_missing_navigation_and_caller_money_are_denied(app,client):
    classroom=initialize_as_teacher('chemistry_p1',client,app);pairs=_attendance(classroom)
    url=_url(client,classroom)
    assert client.get(url.split('?')[0]).status_code==404
    request={'opening_event_id':pairs[0][0],'closing_event_id':pairs[0][1],'reason_code':'INVALID_ATTENDANCE','amount':'1.00'}
    assert client.post(url,json=request).status_code==400
    assert AttendanceIntervalInvalidation.query.count()==0


def test_old_unchecked_payroll_reverse_cannot_write(app,client):
    from tests.dom.prod.test_attendance_invalidation_command import _paid_sources
    classroom=initialize_as_teacher('chemistry_p1',client,app)
    _,ctx,target,pairs,event=_paid_sources(app)
    # The initializer reuses this current class; an unchecked old request is malformed.
    assert client.post(f'/admin/payroll/event/{event.id}/reverse',data={'reason':'old request'}).status_code==400


def test_mobile_dialog_keyboard_focus_and_uncertain_retry(app,client,wcag_live_server):
    import pytest
    from tests.helpers.axe_wcag import authenticated_page,AXE_SOURCE,sync_playwright
    if sync_playwright is None:pytest.skip('Playwright unavailable')
    classroom=initialize_as_teacher('chemistry_p1',client,app);_attendance(classroom)
    url=_detail_url(client,classroom.students[0].seat.public_id)+'&tab=attendance'
    with client.session_transaction() as session:session_data=dict(session)
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        with browser:
            page=authenticated_page(browser,wcag_live_server,session_data);page.set_viewport_size({'width':390,'height':844})
            page.goto(wcag_live_server+url,wait_until='networkidle')
            page.locator('#attendance summary').first.click()
            button=page.get_by_role('button',name='Invalidate work interval');button.focus();page.keyboard.press('Enter')
            modal=page.locator('#attendanceCorrectionModal');modal.wait_for(state='visible')
            confirm=page.locator('#attendanceCorrectionConfirm');confirm.wait_for(state='visible')
            page.wait_for_function("!document.getElementById('attendanceCorrectionConfirm').disabled")
            page.wait_for_function("document.getElementById('attendanceCorrectionReasonCode')===document.activeElement")
            assert 'removed from unpaid earnings' in modal.inner_text()
            page.add_script_tag(content=AXE_SOURCE)
            assert not page.evaluate("async()=> (await axe.run(document.getElementById('attendanceCorrectionModal'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa']}})).violations")
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path='/tmp/attendance-invalidation-mobile.png',full_page=True)
            requests=[]
            def abort_post(route):
                if route.request.method=='POST':requests.append(route.request.post_data_json);route.abort('failed')
                else:route.continue_()
            page.route('**/attendance/invalidation?**',abort_post)
            confirm.click();page.get_by_text('The response could not be confirmed. Retry with the same command key.').wait_for()
            page.wait_for_function("!document.getElementById('attendanceCorrectionConfirm').disabled")
            modal.get_by_role('button',name='Cancel').focus();page.keyboard.press('Enter');modal.wait_for(state='hidden')
            page.wait_for_function("document.activeElement.matches('[data-attendance-correction]')")
            button.click();modal.wait_for(state='visible');confirm.click()
            page.get_by_text('The response could not be confirmed. Retry with the same command key.').wait_for()
            assert len(requests)==2 and requests[0]==requests[1]
            page.context.close()

from tests.helpers.axe_wcag import wcag_live_server  # noqa: F401


def test_csrf_enabled_correction_requires_valid_token(app,client):
    import re
    classroom=initialize_as_teacher('chemistry_p1',client,app);pairs=_attendance(classroom)
    url=_url(client,classroom)
    args={'opening_event_id':pairs[0][0],'closing_event_id':pairs[0][1],'reason_code':'INVALID_ATTENDANCE'}
    p=client.get(url+'&opening_event_id='+str(pairs[0][0])+'&closing_event_id='+str(pairs[0][1])+'&reason_code=INVALID_ATTENDANCE').json
    payload=dict(args,idempotency_key='csrf:correction:1',expected_preview_identity=p['expected_preview_identity'])
    previous=app.config['WTF_CSRF_ENABLED'];app.config['WTF_CSRF_ENABLED']=True
    try:
        html=client.get(_detail_url(client,classroom.students[0].seat.public_id)).get_data(as_text=True)
        token=re.search(r'<meta name="csrf-token" content="([^"]+)"',html).group(1)
        assert client.post(url,json=payload).status_code==400
        assert AttendanceIntervalInvalidation.query.count()==0
        assert client.post(url,json=payload,headers={'X-CSRFToken':token}).status_code==200
    finally:app.config['WTF_CSRF_ENABLED']=previous


def test_class_switch_hides_signed_navigation_and_foreign_source_pair_is_denied(app,client):
    first=initialize_as_teacher('chemistry_p1',client,app);pairs=_attendance(first);url=_url(client,first)
    second=initialize_as_teacher('biology_block_a',client,app);_attendance(second)
    assert client.get(url).status_code==404
    own=_url(client,second)
    response=client.get(own+'&opening_event_id='+str(pairs[0][0])+'&closing_event_id='+str(pairs[0][1])+'&reason_code=INVALID_ATTENDANCE')
    assert response.status_code==400 and response.json['code']=='INCOMPLETE_INTERVAL'


def test_unexpected_atomic_fault_returns_sanitized_500_and_rolls_back(app,client,monkeypatch):
    from app.models import AuditEvent
    classroom=initialize_as_teacher('chemistry_p1',client,app);pairs=_attendance(classroom);url=_url(client,classroom)
    p=client.get(url+'&opening_event_id='+str(pairs[0][0])+'&closing_event_id='+str(pairs[0][1])+'&reason_code=INVALID_ATTENDANCE').json
    before=AuditEvent.query.count()
    import app.feats.attendance_interval_invalidation_feat as feat
    def fail(*args,**kwargs):raise RuntimeError('private internal failure detail')
    monkeypatch.setattr(feat,'audit_protected',fail)
    response=client.post(url,json={'opening_event_id':pairs[0][0],'closing_event_id':pairs[0][1],
        'reason_code':'INVALID_ATTENDANCE','idempotency_key':'route-fault','expected_preview_identity':p['expected_preview_identity']})
    assert response.status_code==500 and response.json['code']=='INTEGRITY_FAILURE'
    assert 'private internal' not in response.get_data(as_text=True)
    assert AttendanceIntervalInvalidation.query.count()==0 and AuditEvent.query.count()==before


def test_personal_notes_and_context_overrides_are_not_command_inputs(app,client):
    classroom=initialize_as_teacher('chemistry_p1',client,app);pairs=_attendance(classroom);url=_url(client,classroom)
    payload={'opening_event_id':pairs[0][0],'closing_event_id':pairs[0][1],'reason_code':'INVALID_ATTENDANCE',
        'idempotency_key':'unsupported-fields','expected_preview_identity':'unused'}
    for field in ('notes','reason','actor_seat_id','class_id','amount'):
        response=client.post(url,json=dict(payload,**{field:'untrusted'}))
        assert response.status_code==400 and response.json['code']=='INVALID_REQUEST'
    assert AttendanceIntervalInvalidation.query.count()==0


def test_paid_mobile_confirmation_recovers_once_after_response_loss(app,client,wcag_live_server):
    import pytest
    from tests.helpers.axe_wcag import authenticated_page,sync_playwright,AXE_SOURCE
    from tests.dom.prod.test_attendance_invalidation_command import _paid_sources
    from app.models import Transaction
    if sync_playwright is None:pytest.skip('Playwright unavailable')
    initialize_as_teacher('chemistry_p1',client,app)
    classroom,ctx,target,pairs,event=_paid_sources(app)
    url=_detail_url(client,classroom.students[0].seat.public_id)+'&tab=attendance'
    correction_url=_url(client,classroom)+'&opening_event_id='+str(pairs[-1][0])+'&closing_event_id='+str(pairs[-1][1])+'&reason_code=INVALID_ATTENDANCE'
    server_preview=client.get(correction_url)
    assert server_preview.status_code==200,server_preview.json
    with client.session_transaction() as session:session_data=dict(session)
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        with browser:
            page=authenticated_page(browser,wcag_live_server,session_data);page.set_viewport_size({'width':390,'height':844})
            page.goto(wcag_live_server+url,wait_until='networkidle');page.locator('#attendance summary').first.click()
            page.get_by_role('button',name='Invalidate work interval').first.click()
            modal=page.locator('#attendanceCorrectionModal');modal.wait_for(state='visible')
            page.wait_for_function("!document.getElementById('attendanceCorrectionConfirm').disabled")
            page.wait_for_function("document.getElementById('attendanceCorrectionReasonCode')===document.activeElement")
            assert 'This correction will recover $' in modal.inner_text()
            assert 'Savings transfer:' in modal.inner_text()
            page.add_script_tag(content=AXE_SOURCE)
            assert not page.evaluate("async()=> (await axe.run(document.getElementById('attendanceCorrectionModal'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa']}})).violations")
            page.screenshot(path='/tmp/attendance-paid-correction-mobile.png',full_page=True)
            requests=[];results=[]
            def lose_first_response(route):
                if route.request.method!='POST':route.continue_();return
                requests.append(route.request.post_data_json)
                response=route.fetch();results.append(response.json())
                if len(requests)==1:route.abort('failed')
                else:route.fulfill(response=response)
            page.route('**/attendance/invalidation?**',lose_first_response)
            confirm=page.locator('#attendanceCorrectionConfirm');confirm.click()
            page.get_by_text('The response could not be confirmed. Retry with the same command key.').wait_for()
            page.wait_for_function("!document.getElementById('attendanceCorrectionConfirm').disabled")
            confirm.click();page.wait_for_function("!document.getElementById('attendanceCorrectionModal').classList.contains('show')")
            assert len(requests)==2 and requests[0]==requests[1]
            assert results[0]['status']=='accepted' and not results[0]['replayed'] and results[1]['replayed']
            assert results[0]['recovery_cents']==results[1]['recovery_cents']
            assert AttendanceIntervalInvalidation.query.count()==1
            assert Transaction.query.filter(Transaction.compensation_amount_cents>0).count()==1
            page.goto(wcag_live_server+'/admin/payroll',wait_until='networkidle')
            page.locator('#history-tab').click()
            assert '$-1.00' in page.locator('#payrollHistoryTable').inner_text()
            page.get_by_role('button',name='Recover payment').first.click()
            page.locator('#attendanceCorrectionModal').wait_for(state='visible')
            page.wait_for_function("!document.getElementById('attendanceCorrectionConfirm').disabled")
            page.wait_for_function("document.getElementById('attendanceCorrectionRefresh')===document.activeElement")
            assert 'remaining payment credit' in page.locator('#attendanceCorrectionConsequence').inner_text()
            assert page.locator('#attendanceCorrectionReason').is_hidden()
            assert 'Invalidation is permanent' not in page.locator('#attendanceCorrectionModal').inner_text()
            page.add_script_tag(content=AXE_SOURCE)
            assert not page.evaluate("async()=> (await axe.run(document.getElementById('attendanceCorrectionModal'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa']}})).violations")
            page.screenshot(path='/tmp/attendance-residual-correction-mobile.png',full_page=True)
            page.context.close()
