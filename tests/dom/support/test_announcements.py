from tests.helpers.support_domain import initialize_support_teacher


def test_DOM_SUP_001__announcement_create_uses_class_id_scope(client):
    initialize_support_teacher("chemistry_p1", client, client.application)

    response = client.get("/admin/announcements/create")

    assert response.status_code == 200
    assert b'name="class_id"' in response.data
    assert b'name="periods"' not in response.data


def _announce(classroom, title):
    from app.extensions import db
    from app.feats.base import FEATContext
    from app.services.announcement_service import create_class_announcement
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"announcement:{title}"):
        announcement = create_class_announcement(
            created_by_seat_id=classroom.teacher_seat.id, class_id=classroom.class_id,
            title=title, message="Body", priority="normal", is_active=True, expires_at=None,
        )
        announcement_id = announcement.id
    db.session.commit()
    return announcement_id


def _stored(announcement_id):
    from app.extensions import db
    from app.models import Announcement
    db.session.expire_all()
    return db.session.get(Announcement, announcement_id)


def test_DOM_SUP_001__announcement_pages_are_class_scoped_without_principal_filter(client):
    """Regression: the pages filtered on the removed Announcement.user_id and 500ed."""
    from tests.helpers.classroom_initializer import initialize
    sibling = initialize("ap_csp_p3", client.application)
    classroom = initialize_support_teacher("chemistry_p1", client, client.application)
    own = _announce(classroom, "Own class notice")
    foreign = _announce(sibling, "Sibling class notice")

    listing = client.get("/admin/announcements")
    assert listing.status_code == 200
    assert b"Own class notice" in listing.data and b"Sibling class notice" not in listing.data
    assert client.get(f"/admin/announcements/edit/{own}").status_code == 200
    assert client.get(f"/admin/announcements/edit/{foreign}").status_code == 302


def test_FEAT_SUP_002__announcement_writes_persist_through_the_feat(client):
    """Regression: every announcement write flushed outside a FEAT and was rolled back.

    Status codes alone cannot show this: create, edit and delete redirect whether
    or not the write landed, so each step asserts the stored row.
    """
    from app.models import Announcement
    from tests.helpers.classroom_initializer import initialize
    sibling = initialize("ap_csp_p3", client.application)
    classroom = initialize_support_teacher("chemistry_p1", client, client.application)
    foreign = _announce(sibling, "Sibling class notice")

    fields = {"class_id": classroom.class_id, "title": "Field trip", "message": "Bring lunch",
              "priority": "normal", "is_active": "y"}
    assert client.post("/admin/announcements/create", data=fields).status_code == 302
    created = Announcement.query.filter_by(class_id=classroom.class_id, title="Field trip").one()
    own = created.id
    assert created.created_by_seat_id == classroom.teacher_seat.id

    fields["title"] = "Field trip moved"
    assert client.post(f"/admin/announcements/edit/{own}", data=fields).status_code == 302
    assert _stored(own).title == "Field trip moved"

    toggled = client.post(f"/admin/announcements/toggle/{own}")
    assert toggled.status_code == 200 and toggled.get_json()["is_active"] is False
    assert _stored(own).is_active is False

    assert client.post(f"/admin/announcements/toggle/{foreign}").status_code == 404
    assert client.post(f"/admin/announcements/delete/{foreign}").status_code == 302
    assert _stored(foreign) is not None and _stored(foreign).is_active is True

    assert client.post(f"/admin/announcements/delete/{own}").status_code == 302
    assert _stored(own) is None
