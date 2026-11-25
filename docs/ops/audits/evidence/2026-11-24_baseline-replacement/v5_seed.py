"""V5 synthetic source state at d7a3e9b1c5f2, written by the v2.0.0 application itself.

Run from the v2.0.0 worktree with its own venv. Synthetic identities only (the
SPEC-TEST-001 canonical roster), test-only keys, a disposable *_test database.
"""
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.getcwd())
os.environ.update(
    FLASK_ENV="testing", SECRET_KEY="test-secret", PEPPER_KEY="test-primary-pepper",
    PEPPER_LEGACY_KEYS="legacy-pepper", PEPPER="legacy-pepper", RATELIMIT_STORAGE_URI="memory://",
    ENCRYPTION_KEY="jhe53bcYZI4_MZS4Kb8hu8-xnQHHvwqSX8LN4sDtzbw=",
    AUDIT_HMAC_KEY="test-audit-hmac-key-for-tests-only-not-for-production",
)
assert os.environ["DATABASE_URL"].rsplit("/", 1)[1].endswith("_test")
os.environ["TEST_DATABASE_URL"] = os.environ["DATABASE_URL"]

from app import app, db  # noqa: E402
from app.feats.base import FEATContext  # noqa: E402
from tests.helpers.classroom_initializer import initialize  # noqa: E402
from tests.helpers.ledger import (  # noqa: E402
    create_ledger_idempotent_transaction, create_ledger_transfer_pair, settle_ledger_balances,
)
from tests.helpers.store_products import publish_store_product  # noqa: E402
from tests.helpers.support_domain import seed_support_issue_categories  # noqa: E402
from app.utils.issue_helpers import create_issue  # noqa: E402
from app.models import IssueCategory  # noqa: E402
from app.services.payroll_settings_service import upsert_payroll_settings  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

# The v2.0.0 provisioning helper hand-builds a dateless PayrollSettings row as a test
# convenience; the admin form (the only production writer) always supplies
# first_pay_date, and post-launch a7e3c9d1f5b2 refuses dateless rows. Date it here so
# the synthetic state is one production could hold.
import tests.helpers.canonical_classroom as _cc  # noqa: E402
_PayrollSettings = _cc.PayrollSettings
def _dated_payroll_settings(**fields):
    fields.setdefault("first_pay_date", datetime(2026, 9, 1, 16, 0, tzinfo=timezone.utc))
    return _PayrollSettings(**fields)
_cc.PayrollSettings = _dated_payroll_settings

app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
with app.app_context():
    rooms = [initialize(key, app) for key in ("chemistry_p1", "ap_csp_p3", "biology_block_a", "unicode")]
    seed_support_issue_categories()
    category = IssueCategory.query.order_by(IssueCategory.id).first()
    for r, room in enumerate(rooms):
        # The admin payroll form's write path (routes/admin.py -> upsert_payroll_settings).
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"v5:{room.class_id}:payroll"):
            upsert_payroll_settings(class_id=room.class_id, settings_data={
                "first_pay_date": datetime(2026, 9, 4 + r, 16, 0, tzinfo=timezone.utc)})
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"v5:{room.class_id}:product"):
            publish_store_product(class_id=room.class_id, entitlement_type="HALL_PASS",
                                  name=f"Pass {r}", price="2.00")
        for i, student in enumerate(room.students):
            seat_id = student.seat.id
            key = f"v5:{room.class_id}:{seat_id}"
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"{key}:pay"):
                create_ledger_idempotent_transaction(
                    idempotency_key=f"{key}:pay", seat_id=seat_id, class_id=room.class_id,
                    amount=Decimal(50 + 7 * i + r), account_type="checking", type="payroll",
                    description="Synthetic payroll", actor_seat_id=room.teacher_seat_id, mechanism="teacher")
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"{key}:settle1"):
                settle_ledger_balances(seat_id, room.class_id)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"{key}:xfer"):
                create_ledger_transfer_pair(
                    seat_id=seat_id, class_id=room.class_id, amount=Decimal("10.00") + i,
                    from_account="checking", to_account="savings",
                    withdraw_description="To savings", deposit_description="From checking")
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"{key}:settle2"):
                settle_ledger_balances(seat_id, room.class_id)
            if i == 0:
                with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"{key}:issue"):
                    create_issue(student.seat, student.user_id, room.class_id, category.id,
                                 "Synthetic ticket", correlation_id=f"{key}:corr", idempotency_key=f"{key}:issue")
        db.session.commit()
    print("seeded", [(room.class_id, len(room.students)) for room in rooms])
