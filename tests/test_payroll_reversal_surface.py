"""Signed FEAT-PROD-003 full/residual recovery surface and original lineage."""
from app.models import PayrollEvent,Transaction
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.dom.prod.test_attendance_invalidation_command import _paid_sources


def _payment(app,client):
    classroom=initialize_as_teacher('chemistry_p1',client,app)
    source,ctx,target,pairs,event=_paid_sources(app)
    return source,event


def _preview(client,event):return client.get(f'/admin/payroll/event/{event.id}/recovery-preview')

def _confirm(client,event,p,key='surface:recovery:1'):
    return client.post(f'/admin/payroll/event/{event.id}/reverse',json={'idempotency_key':key,'expected_preview_identity':p['expected_preview_identity']})


def test_a_payroll_entry_can_be_reversed_from_the_payroll_page(app,client):
    classroom,event=_payment(app,client); original_summary=event.summary_json.copy(); correlation=event.correlation_id
    p=_preview(client,event); assert p.status_code==200 and p.json['recovery_kind']=='EXACT_REVERSAL'
    response=_confirm(client,event,p.json); assert response.status_code==200,response.data
    reversal=PayrollEvent.query.filter_by(class_id=classroom.class_id,payroll_event_type='reversal').one()
    assert reversal.correlation_id==correlation and reversal.target_seat_id==event.target_seat_id
    assert PayrollEvent.query.filter_by(id=event.id).one().summary_json==original_summary
    credit=Transaction.query.filter_by(idempotency_key='correction-original').one()
    counter=Transaction.query.filter_by(compensation_origin_locator=f'ledger-credit:v1:{credit.id}').one()
    assert counter.amount==-credit.amount and counter.compensation_amount_cents==credit.amount_cents


def test_an_entry_cannot_be_reversed_twice(app,client):
    _,event=_payment(app,client);p=_preview(client,event).json
    assert _confirm(client,event,p).status_code==200
    assert _confirm(client,event,p).json['replayed']
    assert _preview(client,event).json['code']=='ALREADY_RECOVERED'
    assert PayrollEvent.query.filter_by(payroll_event_type='reversal').count()==1


def test_a_reversal_cannot_itself_be_reversed(app,client):
    _,event=_payment(app,client);_confirm(client,event,_preview(client,event).json)
    reversal=PayrollEvent.query.filter_by(payroll_event_type='reversal').one()
    assert _preview(client,reversal).status_code==409


def test_reversal_is_scoped_to_the_active_class(app,client):
    _,event=_payment(app,client)
    initialize_as_teacher('biology_block_a',client,app)
    assert _preview(client,event).status_code==404
    assert _confirm(client,event,{'expected_preview_identity':'foreign'}).status_code==404


def test_the_payroll_page_offers_the_control(app,client):
    _,event=_payment(app,client)
    html=client.get('/admin/payroll').get_data(as_text=True)
    assert 'Recover payment' in html and 'recovery-preview' in html
    assert 'onsubmit="return confirm(\'Reverse' not in html


def test_an_entry_with_no_linked_transaction_is_refused_not_500(app,client,monkeypatch):
    _,event=_payment(app,client)
    import app.feats.attendance_interval_invalidation_feat as feat
    monkeypatch.setattr(feat,'resolve_payroll_credit_locator',lambda **kwargs:None)
    response=_preview(client,event)
    assert response.status_code==409 and response.json['code']=='PROVENANCE_UNAVAILABLE'
    assert PayrollEvent.query.filter_by(payroll_event_type='reversal').count()==0


def test_interval_and_residual_history_use_exact_signed_negative_effects(app,client):
    from app.feats.attendance_interval_invalidation_feat import preview_attendance_interval_invalidation,invalidate_attendance_interval
    initialize_as_teacher('chemistry_p1',client,app)
    classroom,ctx,target,pairs,event=_paid_sources(app)
    args=dict(ctx=ctx,target_seat_id=target,opening_event_id=pairs[0][0],closing_event_id=pairs[0][1],reason_code='INVALID_ATTENDANCE')
    p=preview_attendance_interval_invalidation(**args)
    invalidate_attendance_interval(**args,idempotency_key='history-interval',expected_preview_identity=p.identity)
    p=_preview(client,event).json;response=_confirm(client,event,p,key='history-residual')
    assert response.status_code==200
    from app.routes.admin import _build_payroll_event_display_rows
    corrections=PayrollEvent.query.filter_by(class_id=ctx.class_id,payroll_event_type='correction').all()
    rows=_build_payroll_event_display_rows(ctx=ctx,payroll_events=corrections)
    assert len(rows)==2 and all(row['display_amount']=='$-1.00' for row in rows)
    assert '$-1.00' in client.get('/admin/payroll-history').get_data(as_text=True)


def test_missing_correction_proof_is_unavailable_in_all_history_views(app,client,monkeypatch):
    from tests.test_student_detail_attendance_intervals import _detail_url
    classroom,event=_payment(app,client);_confirm(client,event,_preview(client,event).json)
    import app.feats.attendance_interval_invalidation_feat as feat
    monkeypatch.setattr(feat,'verified_creation_evidence',lambda *args,**kwargs:None)
    for url in ('/admin/payroll','/admin/payroll-history',_detail_url(client,classroom.students[0].seat.public_id)):
        response=client.get(url);assert response.status_code==200,response.data
        html=response.get_data(as_text=True)
        assert 'Contribution unavailable' in html
    html=client.get(_detail_url(client,classroom.students[0].seat.public_id)).get_data(as_text=True)
    assert 'Total unavailable' in html


def test_missing_and_malformed_correction_locators_never_fabricate_zero(app,client):
    from app.feats.base import FEATContext,audit_protected
    from app.utils.audit_verifier import PROTECTED_FIELDS_BY_TABLE
    from app.extensions import db
    from app.routes.admin import _build_payroll_event_display_rows
    from tests.test_student_detail_attendance_intervals import _detail_url
    from datetime import datetime,timezone
    classroom,event=_payment(app,client)
    from app.services.context_resolver import CanonicalContext
    ctx=CanonicalContext(classroom.teacher_user.id,event.class_id,classroom.teacher_seat.id,'teacher')
    cases=[('correction',{}),('correction',{'ledger_result_locator':'malformed'}),('reversal',{'command_receipt':{}})]
    records=[]
    for index,(kind,summary) in enumerate(cases):
        with FEATContext('FEAT-PROD-003',idempotency_key=f'unprovable-correction:{index}'):
            record=PayrollEvent(class_id=event.class_id,target_seat_id=event.target_seat_id,actor_seat_id=ctx.seat_id,
                correlation_id=f'corr_unprovable-correction:{index}',idempotency_key=f'unprovable-correction:{index}',
                policy_uuid=event.policy_uuid,mechanism='TEACHER',payroll_event_type=kind,recorded_at=datetime.now(timezone.utc),summary_json=summary)
            db.session.add(record);db.session.flush();audit_protected('payroll_event',record,'INSERT',PROTECTED_FIELDS_BY_TABLE['payroll_event'])
            records.append(record)
    rows=_build_payroll_event_display_rows(ctx=ctx,payroll_events=records)
    assert all(row['amount'] is None and row['display_amount']=='Contribution unavailable' for row in rows)
    for url in ('/admin/payroll','/admin/payroll-history',_detail_url(client,classroom.students[0].seat.public_id)):
        response=client.get(url);assert response.status_code==200,response.data
        assert 'Contribution unavailable' in response.get_data(as_text=True)
