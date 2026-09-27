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


def is_trivially_weak_reset_code(code: str) -> bool:
    """FEAT-IDEN-003 §III.B Step 1: reject one repeated character, or a run
    that steps by one through ``RESET_CODE_ALPHABET`` in either direction."""
    if len(set(code)) == 1:
        return True
    positions = [RESET_CODE_ALPHABET.find(char) for char in code]
    if -1 in positions:
        return False
    steps = {b - a for a, b in zip(positions, positions[1:])}
    return steps in ({1}, {-1})


def _generate_reset_code() -> str:
    while True:
        code = "".join(secrets.choice(RESET_CODE_ALPHABET) for _ in range(8))
        if not is_trivially_weak_reset_code(code):
            return code


def issue_student_recovery_code(user_id: int) -> str | None:
    user = (User.query.filter_by(id=user_id, user_role="student").populate_existing()
            .with_for_update().one_or_none())
    if user is None:
        return None
    code = _generate_reset_code()
    now = utc_now()
    user.recovery_setup_nonce_hash = None
    user.recovery_setup_expires_at = None
    user.reset_code = code
    user.reset_code_generated_at = now
    user.reset_code_expires_at = now + timedelta(minutes=10)
    db.session.flush()
    return code
