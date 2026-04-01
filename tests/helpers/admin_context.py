from datetime import datetime, timezone


def login_admin(client, admin_id: int, join_code: str | None = None) -> None:
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin_id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
        if join_code is not None:
            sess["current_join_code"] = join_code
