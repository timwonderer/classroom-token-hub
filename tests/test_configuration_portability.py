"""SPEC-CLASS-001 execution acceptance against PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import pytest
from datetime import date
from tests.helpers import temporal
from app.extensions import db
from app.feats.base import FEATContext
from app.feats import configuration_portability as transfer
from app.utils.temporal_display import format_timestamp
from app.models import User, ConfigurationImportReceipt, StoreProduct
from app.services.configuration_artifact import ConfigurationError, sign, verify, StrictJSON
from app.services.context_resolver import CanonicalContext
from tests.helpers.classroom_initializer import initialize
from tests.helpers.class_domain import enable_class_feature


def setup_transfer(app):
    classroom = initialize("chemistry_p1", app)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    app.config["CONFIGURATION_EXPORT_KEY"] = "configuration-test-key"
    context = CanonicalContext(user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id, actor_role="teacher")
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"setup:{uuid4()}"):
        db.session.get(User, context.user_id).current_session_nonce = "transfer-test-session"
        transfer.publish_product(class_id=context.class_id, actor_seat_id=context.seat_id,
            definition={"name": "Pencil", "price": 2, "economic_role": "necessity", "item_type": "immediate"})
    return context, "transfer-test-session"


def prepare(context, nonce):
    raw = transfer.export_configuration(context, nonce, {"store": [0]})
    preview = transfer.preview_import(context, nonce, raw)
    return raw, preview["token"]


def test_identical_retry_creates_one_product(app):
    context, nonce = setup_transfer(app)
    raw, token = prepare(context, nonce)
    before = StoreProduct.query.filter_by(class_id=context.class_id).count()
    result = transfer.confirm_import(context, nonce, raw, token)
    assert transfer.confirm_import(context, nonce, raw, token) == result
    assert StoreProduct.query.filter_by(class_id=context.class_id).count() == before + 1


def test_deliberate_import_creates_new_product_identity(app):
    context, nonce = setup_transfer(app)
    raw, token = prepare(context, nonce)
    result = transfer.confirm_import(context, nonce, raw, token)
    second = transfer.preview_import(context, nonce, raw)
    result2 = transfer.confirm_import(context, nonce, raw, second["token"])
    assert result2["store"] != result["store"]


def test_rotation_revokes_successful_retry(app):
    context, nonce = setup_transfer(app)
    raw, token = prepare(context, nonce)
    transfer.confirm_import(context, nonce, raw, token)
    transfer.export_configuration(context, nonce, {"store": [0]})
    with pytest.raises(ConfigurationError, match="replaced"):
        transfer.confirm_import(context, nonce, raw, token)


def test_atomic_failure_has_no_receipt_or_products(app, monkeypatch):
    context, nonce = setup_transfer(app)
    raw, token = prepare(context, nonce)
    before = StoreProduct.query.filter_by(class_id=context.class_id).count()
    def fail(*args, **kwargs):
        raise RuntimeError("audit failed")
    monkeypatch.setattr(transfer, "_audit", fail)
    with pytest.raises(RuntimeError, match="audit failed"):
        transfer.confirm_import(context, nonce, raw, token)
    db.session.remove()
    assert StoreProduct.query.filter_by(class_id=context.class_id).count() == before
    assert ConfigurationImportReceipt.query.filter_by(class_id=context.class_id).count() == 0


def test_concurrent_identical_confirmations(app):
    context, nonce = setup_transfer(app)
    raw, token = prepare(context, nonce)
    db.session.remove()
    barrier = Barrier(2)
    def execute():
        with app.app_context():
            barrier.wait(timeout=10)
            return transfer.confirm_import(context, nonce, raw, token)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = [pool.submit(execute) for _ in range(2)]
        assert a.result(timeout=20) == b.result(timeout=20)
    assert ConfigurationImportReceipt.query.filter_by(class_id=context.class_id).count() == 1
    assert StoreProduct.query.filter_by(class_id=context.class_id).count() == 2


def test_changed_fingerprint_and_revoked_session(app):
    context, nonce = setup_transfer(app)
    raw, token = prepare(context, nonce)
    transfer.confirm_import(context, nonce, raw, token)
    modified = verify(token, "confirmation")
    modified["schedules"] = {"store": {"mode": "exported"}}
    with pytest.raises(ConfigurationError, match="different inputs"):
        transfer.confirm_import(context, nonce, raw, sign(modified, "confirmation"))
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"revoke:{uuid4()}"):
        db.session.get(User, context.user_id).current_session_nonce = "revoked"
    with pytest.raises(ConfigurationError, match="authorization"):
        transfer.confirm_import(context, nonce, raw, token)


def test_strict_json_and_missing_key(app):
    for raw in ['{"a":1,"a":2}', '{"value":NaN}', '{"value":1e999}', '[' * 25 + '0' + ']' * 25]:
        with pytest.raises(ConfigurationError):
            StrictJSON.loads(raw)
    app.config["CONFIGURATION_EXPORT_KEY"] = ""
    with pytest.raises(ConfigurationError, match="not configured"):
        sign({}, "export")


@pytest.mark.parametrize("fail_after_mutations", [False, True])
def test_all_families_share_transaction_and_preserve_payroll_boundary(app, monkeypatch, fail_after_mutations):
    from app.models import PayrollSettings, RentSettings, HallPassSettings, InsurancePolicy, EconomicEngine
    from app.services.payroll.schedule import effective_date_for_new_setting
    from tests.test_insurance_purchase_feat import _submission
    context, nonce = setup_transfer(app)
    for feature in ("insurance", "rent", "hall_pass"):
        enable_class_feature(class_id=context.class_id, feature=feature)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"seed:{uuid4()}"):
        transfer.submit_insurance_definition(class_id=context.class_id, submission=_submission(tier_group="Cover", tier_level=1), actor_seat_id=context.seat_id)
        transfer.save_hall_pass_setup_config(user_id=context.user_id, class_id=context.class_id, hall_pass_enabled=True,
            pass_type_payload=[{"pass_name": "Office", "max_queue": 2, "consume_pass": False}],
            correlation_id=str(uuid4()), idempotency_key=f"hall:{uuid4()}")
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"economy:{uuid4()}"):
        outcome = transfer.evolve_economic_engine(canonical_context=context, class_id=context.class_id,
            updates={"expected_weekly_hours": 5, "interest_rate": 0.01},
            feature_list=list(transfer.get_class_features(context.class_id)))
        assert outcome.success
    raw = transfer.export_configuration(context, nonce)
    preview = transfer.preview_import(context, nonce, raw)
    expected_effective = effective_date_for_new_setting(context.class_id, transfer.identity.now())
    models = [PayrollSettings, RentSettings, HallPassSettings, InsurancePolicy, EconomicEngine]
    before = {model: model.query.filter_by(class_id=context.class_id).count() for model in models}
    if fail_after_mutations:
        def fail(*args, **kwargs):
            raise RuntimeError("final audit failed")
        monkeypatch.setattr(transfer, "_audit", fail)
        with pytest.raises(RuntimeError, match="final audit failed"):
            transfer.confirm_import(context, nonce, raw, preview["token"])
        db.session.remove()
        for model in models:
            assert model.query.filter_by(class_id=context.class_id).count() == before[model]
        assert ConfigurationImportReceipt.query.filter_by(class_id=context.class_id).count() == 0
        return
    from sqlalchemy import event
    commits = []
    session = db.session()
    def record_commit(session):
        commits.append(session.in_nested_transaction())
    event.listen(session, "before_commit", record_commit)
    try:
        result = transfer.confirm_import(context, nonce, raw, preview["token"])
    finally:
        event.remove(session, "before_commit", record_commit)
    assert commits == [False]
    assert result["payroll_effective_at"] == expected_effective.isoformat()
    for model in models:
        assert model.query.filter_by(class_id=context.class_id).count() == before[model] + 1
    assert HallPassSettings.query.filter_by(class_id=context.class_id, availability_state="IN_USE").count() == 1
    assert InsurancePolicy.query.filter_by(class_id=context.class_id, availability_state="IN_USE").count() == 2


def test_expiry_cleanup_does_not_authorize_replay(app, monkeypatch):
    from app.utils.canonical_temporal_resolver import SYSTEM_LEVEL_EVALUATION, canonical_temporal_resolver
    context, nonce = setup_transfer(app)
    raw, token = prepare(context, nonce)
    transfer.confirm_import(context, nonce, raw, token)
    expiry = transfer.identity.instant(verify(raw, "export")["expires_at"])
    after = canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="shift_timestamp",
        timestamp=expiry, elapsed_seconds=1).result["shifted_timestamp_utc"]
    monkeypatch.setattr(transfer.identity, "now", lambda: after)
    with pytest.raises(ConfigurationError, match="expired"):
        transfer.confirm_import(context, nonce, raw, token)
    assert transfer.cleanup_receipts(context, nonce) == 1
    with pytest.raises(ConfigurationError, match="expired"):
        transfer.confirm_import(context, nonce, raw, token)


@pytest.mark.parametrize("change", ["rotation", "session", "expiry"])
def test_waiting_retry_revalidates_after_reference_lock(app, monkeypatch, change):
    from threading import Event
    from sqlalchemy import text, event
    import time
    from app.utils.canonical_temporal_resolver import SYSTEM_LEVEL_EVALUATION, canonical_temporal_resolver
    context, nonce = setup_transfer(app)
    raw, token = prepare(context, nonce)
    transfer.confirm_import(context, nonce, raw, token)
    db.session.remove()
    waiting = Event()
    backend = []
    engine = db.engine
    def observe(conn, cursor, statement, parameters, execution_context, executemany):
        if "FROM users" in statement and "FOR UPDATE" in statement:
            backend.append(conn.connection.driver_connection.get_backend_pid())
            waiting.set()
    event.listen(engine, "before_cursor_execute", observe)
    try:
        with engine.connect() as lock:
            transaction = lock.begin()
            lock.execute(text("SELECT id FROM users WHERE id=:id FOR UPDATE"), {"id": context.user_id})
            def execute():
                with app.app_context():
                    return transfer.confirm_import(context, nonce, raw, token)
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(execute)
                assert waiting.wait(10)
                deadline = time.monotonic() + 10
                while not lock.execute(text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": backend[-1]}).scalar():
                    assert time.monotonic() < deadline
                    time.sleep(.01)
                if change == "rotation":
                    lock.execute(text("UPDATE users SET configuration_export_verifier=:v WHERE id=:id"), {"v": "0" * 64, "id": context.user_id})
                elif change == "session":
                    lock.execute(text("UPDATE users SET current_session_nonce='revoked' WHERE id=:id"), {"id": context.user_id})
                else:
                    expiry = transfer.identity.instant(verify(raw, "export")["expires_at"])
                    after = canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="shift_timestamp", timestamp=expiry, elapsed_seconds=1).result["shifted_timestamp_utc"]
                    monkeypatch.setattr(transfer.identity, "now", lambda: after)
                transaction.commit()
                with pytest.raises(ConfigurationError):
                    future.result(timeout=15)
    finally:
        event.remove(engine, "before_cursor_execute", observe)


def test_class_file_has_no_source_identity_and_imports_into_owned_class(app):
    context, nonce = setup_transfer(app)
    raw, _ = prepare(context, nonce)
    other = initialize("ap_csp_p3", app)
    enable_class_feature(class_id=other.class_id, feature="store")
    destination = CanonicalContext(user_id=other.teacher_user.id, class_id=other.class_id,
        seat_id=other.teacher_seat.id, actor_role="teacher")
    assert destination.user_id == context.user_id
    for forbidden in (context.class_id, 'seat_id', 'policy_uuid', 'product_lineage_uuid', 'tier_group_id'):
        assert forbidden.encode() not in raw
    token = transfer.preview_import(destination, nonce, raw)["token"]
    result = transfer.confirm_import(destination, nonce, raw, token)
    assert StoreProduct.query.filter_by(class_id=destination.class_id, policy_uuid=result["store"][0]).one().name == "Pencil"
    with pytest.raises(ConfigurationError, match="Confirmation does not match"):
        transfer.confirm_import(context, nonce, raw, token)


def test_store_end_dates_roundtrip_without_day_drift(app):
    from datetime import date
    from app.services.configuration_fields import decode, project
    from app.utils.canonical_temporal_resolver import CLASS_LEVEL_EVALUATION, canonical_temporal_resolver
    context, _ = setup_transfer(app)
    end = canonical_temporal_resolver(CLASS_LEVEL_EVALUATION, canonical_execution_context=context,
        primitive="evaluation_day_boundaries", evaluation_date=date(2026, 11, 1)).boundary_end_utc
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"dates:{uuid4()}"):
        product = transfer.publish_product(class_id=context.class_id, actor_seat_id=context.seat_id,
            definition={"name": "Deadline", "price": 2, "economic_role": "necessity", "item_type": "immediate", "auto_delist_date": end})
    values = project(product, "store", context)
    assert values["auto_delist_date"] == "2026-11-01"
    assert decode(values, "store", context)["auto_delist_date"] == end


def test_transfer_page_post_flow_and_get_purity(app, client):
    from tests.test_accessibility import _audit_html_accessibility
    from io import BytesIO
    from bs4 import BeautifulSoup
    from tests.helpers.canonical_session import set_canonical_context
    from app.models import AuditEvent
    context, nonce = setup_transfer(app)
    with client.session_transaction() as session:
        set_canonical_context(session, user_id=context.user_id, class_id=context.class_id,
            seat_id=context.seat_id, role="teacher", nonce=nonce)
    before = AuditEvent.query.count()
    response = client.get("/admin/configuration/")
    assert response.status_code == 200
    assert AuditEvent.query.count() == before
    _audit_html_accessibility(response.get_data(as_text=True))
    inventory_digest = BeautifulSoup(response.data, "html.parser").select_one('input[name="inventory_digest"]')["value"]
    exported = client.post("/admin/configuration/", data={"action": "export", "include_store": "yes", "entry_store": "0", "inventory_digest": inventory_digest})
    assert exported.status_code == 200
    uploaded = client.post("/admin/configuration/", data={"action": "upload", "configuration": (BytesIO(exported.data), "class.cthconfig")})
    assert uploaded.status_code == 200
    assert b"Choose what to import" in uploaded.data
    _audit_html_accessibility(uploaded.get_data(as_text=True))
    preview = client.post("/admin/configuration/", data={"action": "preview", "artifact": exported.data.decode(), "include_store": "yes", "entry_store": "0", "schedule_store": "exported"})
    assert preview.status_code == 200
    _audit_html_accessibility(preview.get_data(as_text=True))
    soup = BeautifulSoup(preview.data, "html.parser")
    confirmation = soup.select_one('input[name="confirmation"]')["value"]
    confirmed = client.post("/admin/configuration/", data={"action": "confirm", "artifact": exported.data.decode(), "confirmation": confirmation})
    assert confirmed.status_code == 200
    assert b"Import complete" in confirmed.data
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        _audit_html_accessibility(client.get("/admin/configuration/").get_data(as_text=True))
        denied = client.post("/admin/configuration/", data={"action": "export"})
        assert denied.status_code == 400
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


def test_rotation_waits_until_import_commits(app, monkeypatch):
    from threading import Event
    from sqlalchemy import event, text
    import time
    context, nonce = setup_transfer(app)
    raw, token = prepare(context, nonce)
    db.session.remove()
    importing, release, rotating = Event(), Event(), Event()
    original = transfer.publish_product
    def pause_publication(**kwargs):
        importing.set()
        assert release.wait(15)
        return original(**kwargs)
    monkeypatch.setattr(transfer, "publish_product", pause_publication)
    engine = db.engine
    backend = []
    def observe(conn, cursor, statement, parameters, execution_context, executemany):
        if importing.is_set() and "FROM users" in statement and "FOR UPDATE" in statement:
            backend.append(conn.connection.driver_connection.get_backend_pid())
            rotating.set()
    event.listen(engine, "before_cursor_execute", observe)
    def run_import():
        with app.app_context():
            return transfer.confirm_import(context, nonce, raw, token)
    def rotate():
        with app.app_context():
            return transfer.export_configuration(context, nonce, {"store": [0]})
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            importing_request = pool.submit(run_import)
            assert importing.wait(10)
            rotation = pool.submit(rotate)
            try:
                assert rotating.wait(10)
                with engine.connect() as connection:
                    deadline = time.monotonic() + 10
                    while not connection.execute(text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": backend[-1]}).scalar():
                        assert time.monotonic() < deadline
                        time.sleep(.01)
            finally:
                release.set()
            result = importing_request.result(timeout=20)
            rotation.result(timeout=20)
        assert ConfigurationImportReceipt.query.filter_by(class_id=context.class_id, operation_id=result["operation_id"]).one()
        assert StoreProduct.query.filter_by(class_id=context.class_id).count() == 2
        with pytest.raises(ConfigurationError, match="replaced"):
            transfer.confirm_import(context, nonce, raw, token)
    finally:
        release.set()
        event.remove(engine, "before_cursor_execute", observe)


def test_class_destruction_cascades_receipts_and_groups(app):
    from app.models import InsuranceTierGroup, ClassEconomy
    from app.services.teacher_destruction import _destroy_class_scope_rows
    context, nonce = setup_transfer(app)
    raw, token = prepare(context, nonce)
    transfer.confirm_import(context, nonce, raw, token)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"group:{uuid4()}"):
        transfer.create_tier_group(context.class_id, "Independent group")
    with FEATContext("FEAT-CLASS-006", idempotency_key=f"destroy:{uuid4()}"):
        _destroy_class_scope_rows(class_id=context.class_id, canonical_context=context)
    assert ClassEconomy.query.filter_by(class_id=context.class_id).count() == 0
    assert ConfigurationImportReceipt.query.filter_by(class_id=context.class_id).count() == 0
    assert InsuranceTierGroup.query.filter_by(class_id=context.class_id).count() == 0


def test_stale_export_selection_and_changed_destination_require_review(app):
    from app.services.configuration_artifact import digest
    context, nonce = setup_transfer(app)
    source_state = digest(StrictJSON.dumps(transfer.inventory(context)))
    raw, token = prepare(context, nonce)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"new:{uuid4()}"):
        transfer.publish_product(class_id=context.class_id, actor_seat_id=context.seat_id,
            definition={"name": "Another item", "price": 3, "economic_role": "necessity", "item_type": "immediate"})
    with pytest.raises(ConfigurationError, match="Review your export"):
        transfer.export_configuration(context, nonce, {"store": [0]}, expected_inventory_digest=source_state)
    with pytest.raises(ConfigurationError, match="Preview the import again"):
        transfer.confirm_import(context, nonce, raw, token)
    assert ConfigurationImportReceipt.query.filter_by(class_id=context.class_id).count() == 0


def test_export_and_upload_limits_fail_without_revoking_current_file(app, monkeypatch):
    from app.services.configuration_artifact import MAX_BYTES
    context, nonce = setup_transfer(app)
    raw, _ = prepare(context, nonce)
    valid = transfer.inventory(context)
    oversized = {"store": valid["store"] * 1001}
    monkeypatch.setattr(transfer, "inventory", lambda context: oversized)
    with pytest.raises(ConfigurationError, match="1,000"):
        transfer.export_configuration(context, nonce)
    user = db.session.get(User, context.user_id)
    transfer.identity.validate_reference(user, verify(raw, "export"))
    with pytest.raises(ConfigurationError, match="1 MiB"):
        sign({"value": "x" * MAX_BYTES}, "export")
    with pytest.raises(ConfigurationError, match="1 MiB"):
        verify(b"x" * (MAX_BYTES + 1), "export")


def test_schedule_choices_keep_receiving_payroll_effective_rule(app):
    from app.services.configuration_fields import project
    from app.services.payroll.settings import current_payroll_setting, payroll_setting_by_uuid
    from app.services.payroll.schedule import effective_date_for_new_setting
    context, nonce = setup_transfer(app)
    destination = project(current_payroll_setting(context.class_id), "payroll", context)
    raw = transfer.export_configuration(context, nonce, {"payroll": True})
    envelope = verify(raw, "export")
    envelope["groups"]["payroll"].update(first_pay_date="2030-12-20", pay_schedule_type="monthly")
    raw = sign(envelope, "export")
    retained = transfer.preview_import(context, nonce, raw, schedules={"payroll": {"mode": "destination"}})
    assert retained["groups"]["payroll"]["first_pay_date"] == destination["first_pay_date"]
    exported = transfer.preview_import(context, nonce, raw, schedules={"payroll": {"mode": "exported"}})
    assert exported["groups"]["payroll"]["first_pay_date"] == "2030-12-20"
    entered = transfer.preview_import(context, nonce, raw, schedules={"payroll": {"mode": "custom", "values": {
        "pay_schedule_type": "weekly", "first_pay_date": "2031-01-15"}}})
    expected = effective_date_for_new_setting(context.class_id, transfer.identity.now())
    result = transfer.confirm_import(context, nonce, raw, entered["token"])
    row = payroll_setting_by_uuid(context.class_id, result["payroll"])
    assert row.effective_date == expected
    assert project(row, "payroll", context)["first_pay_date"] == "2031-01-15"
    with pytest.raises(ConfigurationError, match="no destination schedule"):
        transfer._schedule({"payroll": destination.copy()}, {"payroll": {"mode": "destination"}}, {})
    with pytest.raises(ConfigurationError, match="no destination schedule"):
        transfer._schedule({"store": []}, {"store": {"mode": "destination"}}, {"store": []})


def test_changed_receiving_boundary_requires_new_preview(app, monkeypatch):
    from app.services.payroll import schedule
    context, nonce = setup_transfer(app)
    raw, token = prepare(context, nonce)
    boundary = schedule.effective_date_for_new_setting(context.class_id, transfer.identity.now())
    monkeypatch.setattr(schedule, "effective_date_for_new_setting", lambda *_args: temporal.calendar_days_later(boundary, 7, class_id=context.class_id))
    with pytest.raises(ConfigurationError, match="Preview the import again"):
        transfer.confirm_import(context, nonce, raw, token)
    assert ConfigurationImportReceipt.query.filter_by(class_id=context.class_id).count() == 0


def test_execution_rechecks_http_session_deadline(app):
    from flask import session
    from app.auth import SESSION_TIMEOUT_MINUTES
    context, nonce = setup_transfer(app)
    raw, token = prepare(context, nonce)
    with app.test_request_context("/admin/configuration/", method="POST"):
        session["last_activity"] = temporal.shifted(temporal.now(), minutes=-(SESSION_TIMEOUT_MINUTES + 1)).isoformat()
        with pytest.raises(ConfigurationError, match="session expired"):
            transfer.confirm_import(context, nonce, raw, token)
    assert ConfigurationImportReceipt.query.filter_by(class_id=context.class_id).count() == 0


def test_future_rent_anchor_does_not_hide_invalid_recurrence(app):
    context, _ = setup_transfer(app)
    with pytest.raises(ValueError, match="unsupported frequency_type"):
        transfer._preview_timing(context, {"rent": {
            "first_rent_due_date": temporal.class_wall_time(context.class_id, date(2035, 1, 1), 0),
            "frequency_type": "invalid", "due_day_of_month": 1}})


def test_session_expires_while_waiting_for_class_lock(app, monkeypatch):
    from threading import Event
    from sqlalchemy import text, event
    from flask import session
    from app.auth import SESSION_TIMEOUT_MINUTES
    import time
    context, nonce = setup_transfer(app)
    raw, token = prepare(context, nonce)
    transfer.confirm_import(context, nonce, raw, token)
    before = temporal.now()
    db.session.remove()
    waiting, backend = Event(), []
    engine = db.engine
    def observe(conn, cursor, statement, parameters, execution_context, executemany):
        if "FROM classes" in statement and "FOR UPDATE" in statement:
            backend.append(conn.connection.driver_connection.get_backend_pid())
            waiting.set()
    event.listen(engine, "before_cursor_execute", observe)
    try:
        with engine.connect() as lock:
            transaction = lock.begin()
            lock.execute(text("SELECT class_id FROM classes WHERE class_id=:id FOR UPDATE"), {"id": context.class_id})
            def execute():
                with app.test_request_context("/admin/configuration/", method="POST"):
                    session["last_activity"] = before.isoformat()
                    return transfer.confirm_import(context, nonce, raw, token)
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(execute)
                assert waiting.wait(10)
                deadline = time.monotonic() + 10
                while not lock.execute(text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": backend[-1]}).scalar():
                    assert time.monotonic() < deadline
                    time.sleep(.01)
                monkeypatch.setattr(transfer.identity, "now", lambda: temporal.shifted(before, minutes=SESSION_TIMEOUT_MINUTES + 1))
                transaction.commit()
                with pytest.raises(ConfigurationError, match="session expired"):
                    future.result(timeout=15)
    finally:
        event.remove(engine, "before_cursor_execute", observe)


@pytest.mark.parametrize("calculation,cadence", [("compound", "never"), ("compound", None), ("simple", "daily")])
def test_banking_schedule_rejects_contradictions(app, calculation, cadence):
    from app.services.configuration_fields import SCHEMAS
    context, _ = setup_transfer(app)
    values = {field: None for field in SCHEMAS["banking"]}
    values.update(interest_rate="0.05", interest_calculation_type=calculation, compound_frequency=cadence)
    with pytest.raises(ValueError, match="[Cc]ompound"):
        transfer._validate({"banking": values}, context)
    values.update(interest_calculation_type=None, compound_frequency=None)
    decoded = transfer._validate({"banking": values}, context)["banking"]
    assert decoded["interest_calculation_type"] is None
    assert decoded["compound_frequency"] is None


def test_transfer_displays_class_time_without_changing_receipt_instants(app):
    context, nonce = setup_transfer(app)
    with temporal.pinned_clock(temporal.class_wall_time(context.class_id, date(2030, 1, 15), 9)):
        raw = transfer.export_configuration(context, nonce, {"payroll": True})
        preview = transfer.preview_import(context, nonce, raw)
        envelope = verify(raw, "export")
        assert preview["expires_at"] == "Jan 20, 2030, 9:00 AM PST"
        assert verify(preview["token"], "confirmation")["expires_at"] == envelope["expires_at"]
        result = transfer.confirm_import(context, nonce, raw, preview["token"])
        stored = ConfigurationImportReceipt.query.filter_by(class_id=context.class_id,
            operation_id=result["operation_id"]).one()
        view = transfer.import_result_view(context, result)
        assert view["payroll_effective_display"] == format_timestamp(context, transfer.identity.instant(result["payroll_effective_at"]))
        assert view["payroll_effective_display"].endswith(" PST")
        assert stored.result == result
        assert "payroll_effective_display" not in stored.result
        assert transfer.family_labels(["hall_pass", "store"]) == ["Hall passes", "Store"]
        assert transfer.confirm_import(context, nonce, raw, preview["token"]) == result


def test_preview_values_read_as_teachers_set_them():
    from app.services.configuration_display import preview_sections
    payroll = {"pay_rate": "1.75000000", "overtime_threshold": None, "overtime_threshold_unit": None,
        "max_time_per_day": "90.0", "max_time_per_day_unit": "minutes", "pay_schedule_type": "biweekly",
        "first_pay_date": "2026-11-09"}
    [section] = preview_sections({"payroll": payroll})
    rows = {row["label"]: row["value"] for row in section["blocks"][0]["rows"]}
    assert list(rows) == ["Pay rate", "Overtime after", "Maximum paid time per day", "Pay schedule", "First payday"]
    assert rows == {"Pay rate": "$105.00 per hour", "Overtime after": "Not set",
        "Maximum paid time per day": "90 minutes", "Pay schedule": "Bi-weekly", "First payday": "November 9, 2026"}
    hall = preview_sections({"hall_pass": {"max_queue_limit": 3,
        "pass_type_payload": [{"pass_name": "Bathroom", "max_queue": 2, "consume_pass": True}]}})[0]
    assert section["title"] == "Payroll" and hall["title"] == "Hall passes"
    assert hall["blocks"][0]["rows"][1] == {"label": "Bathroom", "value": "Up to 2 waiting · uses a pass"}
