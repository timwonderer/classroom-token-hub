"""Identity-owned recovery issuance command (DOM-IDEN-002 IX).

The calling FEAT authorizes teacher/class/seat access and owns the transaction.
Both teacher issuance paths compose this command, never a nested FEAT.
"""
from datetime import timedelta
import secrets

from app.extensions import db
from app.models import User
from app.utils.canonical_temporal_resolver import utc_now

RESET_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def issue_student_recovery_code(user_id: int) -> str | None:
    user = (User.query.filter_by(id=user_id, user_role="student").populate_existing()
            .with_for_update().one_or_none())
    if user is None:
        return None
    code = "".join(secrets.choice(RESET_CODE_ALPHABET) for _ in range(8))
    now = utc_now()
    user.recovery_setup_nonce_hash = None
    user.recovery_setup_expires_at = None
    user.reset_code = code
    user.reset_code_generated_at = now
    user.reset_code_expires_at = now + timedelta(minutes=10)
    db.session.flush()
    return code
