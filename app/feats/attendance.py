from __future__ import annotations

from app.extensions import db
from app.models import HallPassSettings
from app.feats.base import requires_feat_context
from app.utils.canonical_temporal_resolver import SYSTEM_LEVEL_EVALUATION, canonical_temporal_resolver


from app.services.hall_pass_configuration import _current_hall_pass_settings, save_hall_pass_setup_config as save_hall_pass_definition

def update_hall_pass_queue_settings(
    *,
    user_id: int,
    class_id: str,
    max_queue_limit: int | None = None,
    updated_at=None,
    correlation_id: str,
    idempotency_key: str,
) -> HallPassSettings:
    """Update class-scoped queue settings for hall-pass management.

    Deliberately *not* decorated with ``@requires_feat_context``. This is a
    thin argument-preparer over ``save_hall_pass_setup_config``, which owns the
    FEAT context. Because ``requires_feat_context`` opens a context
    unconditionally, decorating both meant a FEAT composed a FEAT and every
    call raised ``FEATContextError`` (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2) —
    which made the queue-limit API endpoint an unconditional 500.
    """
    if max_queue_limit is not None:
        try:
            parsed_limit = int(max_queue_limit)
        except (TypeError, ValueError):
            raise ValueError("Queue limit must be between 1 and 50")
        if parsed_limit < 1 or parsed_limit > 50:
            raise ValueError("Queue limit must be between 1 and 50")
    current = _current_hall_pass_settings(class_id)
    if current is None:
        # A queue limit alone is not a hall-pass policy: the teacher sets up
        # destinations first, and nothing is invented for them.
        from app.feats.prod import HallPassSettingsMissing
        raise HallPassSettingsMissing("Hall passes are not set up for this class.")
    return save_hall_pass_setup_config(
        user_id=user_id,
        class_id=class_id,
        hall_pass_enabled=True,
        pass_type_payload=current.get_pass_types(),
        max_queue_limit=parsed_limit if max_queue_limit is not None else current.max_queue_limit,
        updated_at=updated_at,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@requires_feat_context("FEAT-SETTINGS-001")
def save_hall_pass_setup_config(**kwargs):
    return save_hall_pass_definition(**kwargs)


@requires_feat_context("FEAT-SETTINGS-001")
def rotate_teacher_hall_pass_verify_token(*, user_id: int, correlation_id: str, idempotency_key: str) -> str:
    """Rotate and persist a teacher hall-pass verification token on canonical User."""
    from app.models import User
    teacher_user = db.session.get(User, user_id)
    if not teacher_user:
        raise LookupError("User not found.")

    teacher_user.hall_pass_verify_token = User.generate_verify_token()
    db.session.flush()
    return teacher_user.hall_pass_verify_token
