"""Genuine predecessor rows are reconstructed; their signatures stay unchanged."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from flask_migrate import upgrade
from app.extensions import db
from app.models import AuditEvent, AttendanceIntervalInvalidation, Transaction
from app.services.context_resolver import CanonicalContext
from app.feats.attendance_interval_invalidation_feat import (
    preview_attendance_interval_invalidation,
    invalidate_attendance_interval,
    preview_payroll_recovery,
    recover_payroll_payment,
)
from tests.dom.prod.test_historical_v1_assessment import (
    CREATION,
    PREDECESSOR,
    REPOSITORY,
)


def _create(app, tmp_path, *, scenario, rate=None):
    source = tmp_path / "predecessor"
    source.mkdir()
    archive = tmp_path / "predecessor.tar"
    with archive.open("wb") as stream:
        subprocess.run(
            [
                "git",
                "archive",
                (
                    "c42f882b8e610d43f355d684a8632d1fa8d50f72"
                    if scenario == "graph"
                    else PREDECESSOR
                ),
            ],
            cwd=REPOSITORY,
            stdout=stream,
            check=True,
        )
    subprocess.run(["tar", "-xf", str(archive), "-C", str(source)], check=True)
    if scenario == "graph":
        # Configure the archived test setting before its original insertion.
        # No immutable historical business row is repaired after creation.
        fixture = source / "tests/helpers/canonical_classroom.py"
        fixture.write_text(
            fixture.read_text().replace(
                "payroll_frequency_days=14,",
                "payroll_frequency_days=14, first_pay_date=__import__('datetime').date(2026, 9, 28),",
            )
        )
    if scenario == "zero":
        fixture = source / "tests/helpers/canonical_classroom.py"
        fixture.write_text(
            fixture.read_text().replace(
                "pay_rate=Decimal('0.50')", "pay_rate=Decimal('0')"
            )
        )
    if rate is not None:
        fixture = source / "tests/helpers/canonical_classroom.py"
        fixture.write_text(
            fixture.read_text().replace(
                "pay_rate=Decimal('0.50')", f"pay_rate=Decimal('{rate}')"
            )
        )
    script = CREATION
    if scenario == "split":
        start = script.index("    opening=")
        end = script.index("    event=", start)
        script = script[:start] + """    pairs=[]
    for index in range(3):
        opened=at+timedelta(days=index)
        opening=record_attendance_session(ctx=ctx,target_seat_id=target,status='active',mechanism='teacher',idempotency_key=f'v1-open-{index}',reference_time_utc=opened).session
        closing=record_attendance_session(ctx=ctx,target_seat_id=target,status='inactive',mechanism='system',reason_code=AttendanceReasonCode.DONE_FOR_DAY,idempotency_key=f'v1-close-{index}',reference_time_utc=opened+timedelta(seconds=2)).session
        pairs.append([opening.id,closing.id])
""" + script[end:]
        script = script.replace(
            "source=[opening.id,closing.id],", "source=pairs[0],pairs=pairs,"
        )
        script = script.replace(
            "reference_time_utc=at+timedelta(days=1)).payroll_event",
            "reference_time_utc=at+timedelta(days=4)).payroll_event",
        )
    elif scenario == "reversed":
        script = script.replace(
            "    audit=db.session.get",
            """    from app.feats.prod import record_payroll_reversal
    record_payroll_reversal(ctx=ctx,target_seat_id=target,correlation_id=event.correlation_id,
        idempotency_key='v1-reversal',mechanism='TEACHER',
        summary_json={'reversed_payroll_event_id':event.id},reference_time_utc=at+timedelta(days=2))
    with FEATContext('FEAT-LED-003',idempotency_key='v1-reversal-settle'):
        settle_balances(target,ctx.class_id)
    audit=db.session.get""",
        )
    elif scenario == "graph":
        close_start = script.index("    closing=")
        close_end = script.index("    event=", close_start)
        closing = script[close_start:close_end]
        script = script[:close_start] + script[close_end:]
        event_end = script.index("    credit=")
        script = (
            script[:event_end]
            + closing
            + """    record_payroll_event(ctx=ctx,target_seat_id=target,payroll_event_type='payroll',
        correlation_id='corr_v1-zero',idempotency_key='v1-zero',mechanism='TEACHER',reference_time_utc=at+timedelta(days=1))
"""
            + script[event_end:]
        )
        script = script.replace(
            "reference_time_utc=at+timedelta(days=1)).payroll_event",
            "reference_time_utc=at+timedelta(minutes=1)).payroll_event",
        )
        script = script.replace("datetime(2026,8,1,18", "datetime(2026,9,28,18")
        script = script.replace(
            "    at=datetime",
            """    from app.models import PayrollSettings
    from app.services.payroll_settings_service import _activate_payroll_policy_version
    with FEATContext('FEAT-CLASS-005',idempotency_key='legacy-policy'):
        policy=_activate_payroll_policy_version(ctx.class_id,PayrollSettings.query.filter_by(class_id=ctx.class_id).one())
    at=datetime""",
        )
        script = script.replace(
            "payroll_event_type='payroll',",
            "payroll_event_type='payroll',policy_version_id=policy.id,",
        )
    if scenario == "zero":
        script = script.replace(
            "    credit=Transaction.query.filter_by(idempotency_key='v1-credit').one()",
            "    credit=Transaction.query.filter_by(idempotency_key='v1-credit').first()",
        )
        script = script.replace(
            "    audit=db.session.get(AuditEvent,credit.lineage_event_id)",
            '    print("GENUINE_V1="+json.dumps(dict(class_id=ctx.class_id,user_id=ctx.user_id,actor=ctx.seat_id,target=target,event=event.id,source=[opening.id,closing.id])))\n    raise SystemExit(0)\n    audit=db.session.get(AuditEvent,credit.lineage_event_id)',
        )
    environment = dict(
        os.environ, DATABASE_URL=os.environ["TEST_DATABASE_URL"], PYTHONPATH=str(source)
    )
    db.session.remove()
    created = subprocess.run(
        [sys.executable, "-c", script],
        cwd=source,
        env=environment,
        text=True,
        capture_output=True,
        timeout=90,
    )
    assert created.returncode == 0, created.stdout[-3000:] + created.stderr[-3000:]
    record = json.loads(
        next(
            line.partition("=")[2]
            for line in created.stdout.splitlines()
            if line.startswith("GENUINE_V1=")
        )
    )
    if scenario == "graph":
        corrected_source = tmp_path / "correction_writer"
        corrected_source.mkdir()
        with archive.open("wb") as stream:
            subprocess.run(
                ["git", "archive", PREDECESSOR],
                cwd=REPOSITORY,
                stdout=stream,
                check=True,
            )
        subprocess.run(
            ["tar", "-xf", str(archive), "-C", str(corrected_source)], check=True
        )
        correction = r"""
import json,os
from flask_migrate import upgrade
from app import app,db
from app.feats.base import FEATContext
from app.feats.prod import record_payroll_event
from app.services.payroll.corrections import plan_class_corrections
from app.services.context_resolver import CanonicalContext
from app.services.ledger_settlement_service import settle_balances
with app.app_context():
    upgrade()
    result=json.loads(os.environ['HISTORICAL_FIXTURE'])
    ctx=CanonicalContext(result['user_id'],result['class_id'],result['actor'],'teacher')
    postings=plan_class_corrections(ctx=ctx,seat_ids={result['target']})
    assert len(postings)==1
    for posting in postings:
        record_payroll_event(ctx=ctx,target_seat_id=posting.seat_id,payroll_event_type='manual_credit',
            correlation_id=posting.correlation_id,idempotency_key=posting.idempotency_key,mechanism='SYSTEM',
            amount=posting.amount,policy_uuid=posting.policy_uuid,summary_json=posting.summary_json)
    with FEATContext('FEAT-LED-003',idempotency_key='v1-topup-settle'):
        settle_balances(result['target'],result['class_id'])
"""
        corrected = subprocess.run(
            [sys.executable, "-c", correction],
            cwd=corrected_source,
            env=dict(
                environment,
                PYTHONPATH=str(corrected_source),
                HISTORICAL_FIXTURE=json.dumps(record),
            ),
            text=True,
            capture_output=True,
            timeout=90,
        )
        assert corrected.returncode == 0, (
            corrected.stdout[-2000:] + corrected.stderr[-3000:]
        )
    upgrade()
    return record


@pytest.mark.parametrize("scenario", ["paid", "split", "reversed", "graph"])
def test_genuine_v1_reconstruction_recovers_exactly_and_preserves_history(
    app, tmp_path, scenario
):
    record = _create(app, tmp_path, scenario=scenario)
    ctx = CanonicalContext(
        record["user_id"], record["class_id"], record["actor"], "teacher"
    )
    arguments = dict(
        ctx=ctx,
        target_seat_id=record["target"],
        opening_event_id=record["source"][0],
        closing_event_id=record["source"][1],
        reason_code="INVALID_ATTENDANCE",
    )
    preview = preview_attendance_interval_invalidation(**arguments)
    expected = 0 if scenario == "reversed" else 2 if scenario == "split" else 100
    assert preview.public()["recovery_cents"] == expected
    if scenario == "split":
        assert dict(preview.plan.settlement.origins[0].allocations) == {
            tuple(pair): amount for pair, amount in zip(record["pairs"], [2, 2, 1])
        }
    accepted = invalidate_attendance_interval(
        **arguments,
        idempotency_key="new-correction",
        expected_preview_identity=preview.identity,
    )
    assert accepted["recovery_cents"] == expected
    replay = invalidate_attendance_interval(
        **arguments,
        idempotency_key="new-correction",
        expected_preview_identity=preview.identity,
    )
    assert replay["replayed"] and replay["recovery_cents"] == expected
    assert AttendanceIntervalInvalidation.query.count() == 1
    if scenario == "split":
        residual = preview_payroll_recovery(ctx=ctx, payroll_event_id=record["event"])
        assert (
            residual.disposition == "RESIDUAL"
            and residual.public()["recovery_cents"] == 3
        )
        result = recover_payroll_payment(
            ctx=ctx,
            payroll_event_id=record["event"],
            idempotency_key="new-residual",
            expected_preview_identity=residual.identity,
        )
        assert result["recovery_cents"] == 3
        arguments.update(
            opening_event_id=record["pairs"][1][0],
            closing_event_id=record["pairs"][1][1],
        )
        after = preview_attendance_interval_invalidation(**arguments)
        assert after.public()["recovery_cents"] == 0
        invalidate_attendance_interval(
            **arguments,
            idempotency_key="after-recovery",
            expected_preview_identity=after.identity,
        )
    credit = db.session.get(Transaction, record["credit"])
    audit = db.session.get(AuditEvent, credit.lineage_event_id)
    assert [
        credit.lineage_event_id,
        credit.lineage_token,
        credit.lineage_version,
    ] == record["lineage"]
    assert [audit.payload_digest, audit.event_hash, audit.signature_version] == record[
        "audit"
    ]
    assert (
        str(credit.amount) == record["amount"]
        and credit.posting_sequence == record["sequence"]
    )
    assert (
        credit.compensation_origin_locator
        is credit.compensation_amount_cents
        is credit.correction_intent_locator
        is None
    )
    new_effects = Transaction.query.filter(Transaction.lineage_version == 3).all()
    assert sum(row.compensation_amount_cents for row in new_effects) == (
        5 if scenario == "split" else expected
    )
    assert not any(row.type == "overdraft_fee" for row in new_effects)
    if scenario == "graph":
        assert len(preview.plan.principals) == 2
        assert len({row.command_reservation_id for row in new_effects}) == 1


def _arguments(record):
    ctx = CanonicalContext(
        record["user_id"], record["class_id"], record["actor"], "teacher"
    )
    return dict(
        ctx=ctx,
        target_seat_id=record["target"],
        opening_event_id=record["source"][0],
        closing_event_id=record["source"][1],
        reason_code="INVALID_ATTENDANCE",
    )


def test_genuine_historical_zero_payment_is_eligibility_only_with_business_receipt(
    app, tmp_path
):
    record = _create(app, tmp_path, scenario="zero")
    arguments = _arguments(record)
    before = Transaction.query.count()
    preview = preview_attendance_interval_invalidation(**arguments)
    assert preview.disposition == "ZERO_CENT"
    assert preview.public()["recovery_cents"] == 0
    result = invalidate_attendance_interval(
        **arguments,
        idempotency_key="zero-invalidation",
        expected_preview_identity=preview.identity,
    )
    assert result["recovery_cents"] == 0 and Transaction.query.count() == before
    row = AttendanceIntervalInvalidation.query.one()
    assert row.receipt_json["opaque_outcome_locators"]["original_payroll_events"] == [
        f"prod-payroll:v1:{record['event']}"
    ]
    assert row.receipt_json["opaque_outcome_locators"]["ledger_origins"] == []
    assert invalidate_attendance_interval(
        **arguments,
        idempotency_key="zero-invalidation",
        expected_preview_identity=preview.identity,
    )["replayed"]


def test_genuine_pending_historical_payroll_denial_is_normalized(
    app, tmp_path, monkeypatch
):
    from app.services.attendance_invalidation_service import AttendanceCorrectionDenied

    record = _create(app, tmp_path, scenario="paid")
    # Exercise a historical credit above the currently observed scope cursor.
    # Immutable transactions/signatures are never changed for this state probe.
    import app.services.ledger_historical_reconstruction as reconstruction

    monkeypatch.setattr(
        reconstruction,
        "get_account_posting_boundary",
        lambda *args, **kwargs: 0,
    )
    with pytest.raises(AttendanceCorrectionDenied, match="PAYROLL_PENDING"):
        preview_attendance_interval_invalidation(**_arguments(record))
    assert AttendanceIntervalInvalidation.query.count() == 0


def test_genuine_historical_full_reversal_preserves_original_correlation_and_signature(
    app, tmp_path
):
    record = _create(app, tmp_path, scenario="paid")
    arguments = _arguments(record)
    original = db.session.get(Transaction, record["credit"])
    original_correlation = original.correlation_id
    preview = preview_payroll_recovery(
        ctx=arguments["ctx"], payroll_event_id=record["event"]
    )
    assert preview.disposition == "EXACT_REVERSAL"
    recover_payroll_payment(
        ctx=arguments["ctx"],
        payroll_event_id=record["event"],
        idempotency_key="historical-exact",
        expected_preview_identity=preview.identity,
    )
    reversal = Transaction.query.filter_by(type="REVERSAL", lineage_version=3).one()
    assert reversal.correlation_id == original_correlation
    assert original.reversal_transaction_id is None
    assert [
        original.lineage_event_id,
        original.lineage_token,
        original.lineage_version,
    ] == record["lineage"]
    audit = db.session.get(AuditEvent, original.lineage_event_id)
    assert [audit.payload_digest, audit.event_hash, audit.signature_version] == record[
        "audit"
    ]
    assert (
        preview_attendance_interval_invalidation(**arguments).public()["recovery_cents"]
        == 0
    )


@pytest.mark.parametrize("principal_count", [0, 2])
def test_historical_payment_recovery_rejects_invalid_principal_count_atomically(
    app, tmp_path, monkeypatch, principal_count
):
    import app.feats.attendance_interval_invalidation_feat as command
    from app.models import PayrollEvent, LedgerCommandReservation

    record = _create(app, tmp_path, scenario="paid")
    arguments = _arguments(record)
    preview = preview_payroll_recovery(
        ctx=arguments["ctx"], payroll_event_id=record["event"]
    )
    models = (Transaction, PayrollEvent, AuditEvent, LedgerCommandReservation)
    before = tuple(model.query.count() for model in models)
    apply_recovery = command.apply_reconstructed_recovery

    def malformed_result(**kwargs):
        # Exercise rollback after real reservation/effect writes,
        # rather than replacing the monetary command with a no-op.
        result = apply_recovery(**kwargs)
        assert len(result["principals"]) == 1
        return dict(result, principals=result["principals"] * principal_count)

    monkeypatch.setattr(command, "apply_reconstructed_recovery", malformed_result)
    with pytest.raises(command.AttendanceCorrectionDenied) as denied:
        recover_payroll_payment(
            ctx=arguments["ctx"],
            payroll_event_id=record["event"],
            idempotency_key="historical-malformed-principals",
            expected_preview_identity=preview.identity,
        )
    assert denied.value.code == "INTEGRITY_FAILURE"
    assert tuple(model.query.count() for model in models) == before
    original = db.session.get(Transaction, record["credit"])
    assert original.reversal_transaction_id is None
    assert [original.lineage_event_id, original.lineage_token, original.lineage_version] == record["lineage"]
    audit = db.session.get(AuditEvent, original.lineage_event_id)
    assert [audit.payload_digest, audit.event_hash, audit.signature_version] == record["audit"]


@pytest.mark.parametrize("point", ["business", "audit", "reservation"])
def test_genuine_historical_recovery_failure_rolls_back_all_effects(
    app, tmp_path, monkeypatch, point
):
    import app.feats.attendance_interval_invalidation_feat as command
    import app.services.ledger_command_service as ledger_command

    record = _create(app, tmp_path, scenario="paid")
    arguments = _arguments(record)
    preview = preview_attendance_interval_invalidation(**arguments)
    from app.models import PayrollEvent, LedgerCommandReservation

    models = (
        Transaction,
        PayrollEvent,
        AttendanceIntervalInvalidation,
        AuditEvent,
        LedgerCommandReservation,
    )
    before = tuple(model.query.count() for model in models)

    def fail(*args, **kwargs):
        raise RuntimeError("injected historical failure")

    if point == "reservation":
        monkeypatch.setattr(ledger_command, "create_reserved_effects", fail)
    elif point == "business":
        monkeypatch.setattr(command, "record_payroll_business_correction", fail)
    else:
        monkeypatch.setattr(command, "audit_protected", fail)
    with pytest.raises(RuntimeError, match="injected historical failure"):
        invalidate_attendance_interval(
            **arguments,
            idempotency_key="failed-historical",
            expected_preview_identity=preview.identity,
        )
    assert tuple(model.query.count() for model in models) == before


@pytest.mark.parametrize(
    "savings,enabled,transfer,checking_after,savings_after",
    [
        ("3", True, "0", "-8", "3"),
        ("9", True, "8", "0", "1"),
        ("9", False, "0", "-8", "9"),
    ],
)
def test_genuine_multi_origin_recovery_resolves_aggregate_protection_once(
    app, tmp_path, savings, enabled, transfer, checking_after, savings_after
):
    from datetime import datetime, timezone
    from decimal import Decimal
    from app.feats.base import FEATContext
    from app.models import EconomicEngine
    from app.services.ledger_balance_query_service import get_available_balances
    from tests.helpers.ledger import record_ledger_fixture

    record = _create(app, tmp_path, scenario="graph", rate="5")
    arguments = _arguments(record)
    current = (
        EconomicEngine.query.filter_by(class_id=record["class_id"])
        .order_by(EconomicEngine.created_at.desc())
        .first()
    )
    with FEATContext("FEAT-SETTINGS-001", idempotency_key="historical-protection"):
        instant = datetime.now(timezone.utc)
        engine = EconomicEngine(
            class_id=record["class_id"],
            economic_version_id="historical-protection",
            previous_version_id=current.economic_version_id,
            economy_policy_mode=current.economy_policy_mode,
            overdraft_protection_enabled=enabled,
            created_at=instant,
            effective_at=instant,
        )
        db.session.add(engine)
        db.session.flush()
    with FEATContext("FEAT-LED-001", idempotency_key="historical-balance-inputs"):
        record_ledger_fixture(
            seat_id=record["target"],
            class_id=record["class_id"],
            amount=Decimal("-8"),
            posted=True,
        )
        record_ledger_fixture(
            seat_id=record["target"],
            class_id=record["class_id"],
            amount=Decimal(savings),
            account_type="savings",
            posted=True,
        )
    assert get_available_balances(record["target"], record["class_id"]) == (
        Decimal("2"),
        Decimal(savings),
    )
    preview = preview_attendance_interval_invalidation(**arguments)
    assert (
        preview.public()["recovery_cents"] == 1000 and len(preview.plan.principals) == 2
    )
    assert Decimal(preview.public()["protection_transfer"]) == Decimal(transfer)
    invalidate_attendance_interval(
        **arguments,
        idempotency_key="aggregate-recovery",
        expected_preview_identity=preview.identity,
    )
    assert get_available_balances(record["target"], record["class_id"]) == (
        Decimal(checking_after),
        Decimal(savings_after),
    )
    effects = Transaction.query.filter(
        Transaction.lineage_version == 3, Transaction.command_reservation_id.isnot(None)
    ).all()
    assert len({effect.command_reservation_id for effect in effects}) == 1
    assert sum(effect.compensation_amount_cents for effect in effects) == 1000
    assert all(
        effect.compensation_amount_cents == 0
        for effect in effects
        if effect.type in ("Withdrawal", "Deposit")
    )
    assert not any(effect.type == "overdraft_fee" for effect in effects)


def test_genuine_historical_chain_tampering_blocks_reconstruction(app, tmp_path):
    from sqlalchemy import text
    from app.services.attendance_invalidation_service import AttendanceCorrectionDenied

    record = _create(app, tmp_path, scenario="paid")
    assert "test" in db.engine.url.database
    # Deliberately corrupt an isolated database to exercise actual verifier denial.
    with db.engine.begin() as connection:
        connection.execute(text("ALTER TABLE audit_events DISABLE TRIGGER USER"))
        connection.execute(
            text("UPDATE audit_events SET event_hash=:bad WHERE id=:id"),
            {"bad": "0" * 64, "id": record["lineage"][0]},
        )
        connection.execute(text("ALTER TABLE audit_events ENABLE TRIGGER USER"))
    db.session.expire_all()
    with pytest.raises(AttendanceCorrectionDenied, match="INTEGRITY_FAILURE"):
        preview_attendance_interval_invalidation(**_arguments(record))
    assert AttendanceIntervalInvalidation.query.count() == 0


def test_signed_partial_debit_cannot_claim_residual_recovery(
    app, tmp_path, monkeypatch
):
    import app.feats.attendance_interval_invalidation_feat as command
    from app.services.attendance_invalidation_service import AttendanceCorrectionDenied

    record = _create(app, tmp_path, scenario="split")
    arguments = _arguments(record)
    preview = preview_attendance_interval_invalidation(**arguments)
    writer = command.record_payroll_business_correction

    def mislabeled_writer(**kwargs):
        # Fault injection changes new business intent before INSERT/signing.
        # Existing rows and original signature versions are never edited.
        kwargs["correction_intent"] = "RESIDUAL_RECOVERY"
        return writer(**kwargs)

    monkeypatch.setattr(
        command, "record_payroll_business_correction", mislabeled_writer
    )
    invalidate_attendance_interval(
        **arguments,
        idempotency_key="mislabeled-new-recovery",
        expected_preview_identity=preview.identity,
    )
    arguments.update(
        opening_event_id=record["pairs"][1][0], closing_event_id=record["pairs"][1][1]
    )
    with pytest.raises(AttendanceCorrectionDenied, match="INTEGRITY_FAILURE"):
        preview_attendance_interval_invalidation(**arguments)


def test_mixed_historical_and_current_payments_keep_strict_current_creation_evidence(
    app, tmp_path
):
    from datetime import datetime, timedelta, timezone
    from app.feats.prod import record_attendance_session, record_payroll_event
    from app.feats.base import FEATContext
    from app.models import AttendanceReasonCode
    from app.services.ledger_settlement_service import settle_balances
    from app.utils.audit_verifier import verified_creation_evidence

    record = _create(app, tmp_path, scenario="paid")
    arguments = _arguments(record)
    ctx = arguments["ctx"]
    at = datetime(2026, 8, 5, 18, tzinfo=timezone.utc)
    record_attendance_session(
        ctx=ctx,
        target_seat_id=record["target"],
        status="active",
        mechanism="teacher",
        idempotency_key="current-open",
        reference_time_utc=at,
    )
    record_attendance_session(
        ctx=ctx,
        target_seat_id=record["target"],
        status="inactive",
        mechanism="system",
        reason_code=AttendanceReasonCode.DONE_FOR_DAY,
        idempotency_key="current-close",
        reference_time_utc=at + timedelta(minutes=2),
    )
    event = record_payroll_event(
        ctx=ctx,
        target_seat_id=record["target"],
        payroll_event_type="payroll",
        correlation_id="corr_current-payment",
        idempotency_key="current-payment",
        mechanism="TEACHER",
        reference_time_utc=at + timedelta(days=1),
    ).payroll_event
    with FEATContext("FEAT-LED-003", idempotency_key="current-settle"):
        settle_balances(record["target"], record["class_id"])
    assert (
        verified_creation_evidence("payroll_event", event, record["class_id"])
        is not None
    )
    preview = preview_attendance_interval_invalidation(**arguments)
    assert {origin.event_id for origin in preview.plan.settlement.origins} == {
        record["event"],
        event.id,
    }
    assert preview.public()["recovery_cents"] == 100
    invalidate_attendance_interval(
        **arguments,
        idempotency_key="mixed-current-reconstruction",
        expected_preview_identity=preview.identity,
    )
    assert (
        verified_creation_evidence("payroll_event", event, record["class_id"])
        is not None
    )


@pytest.mark.parametrize("first_kind", ["interval", "payment"])
def test_genuine_historical_concurrent_recovery_caps_include_pending_effects(
    app, tmp_path, monkeypatch, first_kind
):
    from app.feats import attendance_interval_invalidation_feat as command
    from tests.dom.prod.test_attendance_correction_concurrency import (
        _ordered_race,
        _invalidate,
        _recover,
    )

    record = _create(app, tmp_path, scenario="split")
    arguments = _arguments(record)
    interval = _invalidate(
        arguments, preview_attendance_interval_invalidation(**arguments).identity
    )
    payment = _recover(
        arguments["ctx"],
        record["event"],
        preview_payroll_recovery(
            ctx=arguments["ctx"], payroll_event_id=record["event"]
        ).identity,
    )
    first, second = (
        (interval, payment) if first_kind == "interval" else (payment, interval)
    )
    outcomes = _ordered_race(
        app, monkeypatch, first, second, [(command, "lock_recovery_scope")]
    )
    assert outcomes[0][0] == "accepted"
    assert outcomes[1] == ("denied", "PREVIEW_CHANGED")
    assert (
        sum(row.compensation_amount_cents or 0 for row in Transaction.query.all()) <= 5
    )
    if first_kind == "interval":
        residual = preview_payroll_recovery(
            ctx=arguments["ctx"], payroll_event_id=record["event"]
        )
        assert residual.public()["recovery_cents"] == 3
        _recover(arguments["ctx"], record["event"], residual.identity)()
    assert (
        sum(row.compensation_amount_cents or 0 for row in Transaction.query.all()) == 5
    )


def test_historical_preview_ignores_unrelated_open_interval_clock(
    app, tmp_path, monkeypatch
):
    from datetime import datetime, timedelta, timezone
    from app.feats.prod import record_attendance_session
    import app.utils.canonical_temporal_resolver as temporal

    record = _create(app, tmp_path, scenario="paid")
    arguments = _arguments(record)
    record_attendance_session(
        ctx=arguments["ctx"],
        target_seat_id=record["target"],
        status="active",
        mechanism="teacher",
        idempotency_key="unrelated-current-open",
        reference_time_utc=datetime(2026, 8, 4, 18, tzinfo=timezone.utc),
    )
    now = datetime(2026, 10, 3, 18, tzinfo=timezone.utc)
    monkeypatch.setattr(temporal, "utc_now", lambda: now)
    first = preview_attendance_interval_invalidation(**arguments)
    monkeypatch.setattr(temporal, "utc_now", lambda: now + timedelta(minutes=10))
    second = preview_attendance_interval_invalidation(**arguments)
    assert first.identity == second.identity
    invalidate_attendance_interval(
        **arguments,
        idempotency_key="stable-historical-preview",
        expected_preview_identity=first.identity,
    )



def test_historical_payroll_excludes_only_proven_unrelated_modern_reversal(app, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app.feats.base import FEATContext
    from app.feats import attendance_interval_invalidation_feat as command
    from app.services.ledger_historical_reconstruction import _proven_unrelated_reversal
    from app.services.ledger_recovery_service import ledger_origin_locator
    from tests.helpers.ledger import record_ledger_fixture, compensate_ledger_posted_transaction

    record = _create(app, tmp_path, scenario="paid")
    args = _arguments(record)
    before = preview_attendance_interval_invalidation(**args).public()["recovery_cents"]
    with FEATContext("FEAT-LED-001", idempotency_key="unrelated-credit"):
        unrelated = record_ledger_fixture(
            seat_id=record["target"], target_seat_id=record["target"],
            class_id=record["class_id"], actor_seat_id=record["actor"],
            amount=2, type="insurance_reimbursement", mechanism="teacher", posted=True,
        )
    with FEATContext("FEAT-LED-002", idempotency_key="unrelated-reversal"):
        reversal = compensate_ledger_posted_transaction(
            unrelated, description="Unrelated refund", idempotency_key="unrelated-reversal",
            actor_seat_id=record["actor"],
        )
    preview = preview_attendance_interval_invalidation(**args)
    assert preview.public()["recovery_cents"] == before
    settlement, _, proofs = command._historical_settlement(args["ctx"], record["target"])
    locators = {origin.proof.origin_locator for origin in settlement.origins}
    records_by_locator = {ledger_origin_locator(unrelated): unrelated}
    assert _proven_unrelated_reversal(reversal, locators, records_by_locator, settlement.creation_evidence)
    assert not _proven_unrelated_reversal(reversal, locators, records_by_locator, ())
    malformed = SimpleNamespace(**{column.key: getattr(reversal, column.key) for column in Transaction.__table__.columns})
    malformed.original_transaction_id = 99999999
    assert not _proven_unrelated_reversal(malformed, locators, records_by_locator, settlement.creation_evidence)
    # Removing verified signed-origin evidence must still deny the public
    # preview instead of trusting an unsigned original ID or ignoring the row.
    creation_proofs = command.ledger_creation_proofs
    with monkeypatch.context() as patch:
        patch.setattr(command, "ledger_creation_proofs", lambda rows, class_id: tuple(
            proof for proof in creation_proofs(rows, class_id) if proof.row_pk != str(reversal.id)
        ))
        with pytest.raises(command.AttendanceCorrectionDenied, match="PROVENANCE_UNAVAILABLE"):
            preview_attendance_interval_invalidation(**args)
    result = invalidate_attendance_interval(
        **args, idempotency_key="payroll-beside-unrelated-reversal", expected_preview_identity=preview.identity,
    )
    assert result["recovery_cents"] == before
    assert [db.session.get(Transaction, record["credit"]).lineage_event_id,
            db.session.get(Transaction, record["credit"]).lineage_token,
            db.session.get(Transaction, record["credit"]).lineage_version] == record["lineage"]
