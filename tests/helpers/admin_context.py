from datetime import datetime, timezone


def login_admin(
    client,
    admin_id: int,
    join_code: str | None = None,
    *,
    user_id: int | None = None,
    class_id: str | None = None,
    seat_id: int | None = None,
) -> None:
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin_id
        if user_id is not None:
            sess["user_id"] = user_id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
        if join_code is not None:
            sess["current_join_code"] = join_code
        if class_id is not None:
            sess["current_class_id"] = class_id
        if seat_id is not None:
            sess["current_seat_id"] = seat_id
