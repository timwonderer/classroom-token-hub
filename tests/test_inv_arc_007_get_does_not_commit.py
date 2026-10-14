"""INV-ARC-007: a GET must not commit.

These three routes once wrapped the whole view in ``@requires_feat_context``, so
every page load opened a FEAT and committed on exit (310 commits from
``GET /student/login`` in one school day). The FEAT now wraps only the submission.
``semgrep/cth-get-must-be-pure.yaml`` guards the pattern statically; this checks
the behavior.
"""
from contextlib import contextmanager

import pytest
from sqlalchemy import event

from app.extensions import db
from app.models import User
from tests.helpers.classroom_initializer import initialize_as_teacher


@contextmanager
def _commits():
    count = [0]

    def on_commit(session):
        count[0] += 1

    event.listen(db.session, "after_commit", on_commit)
    try:
        yield count
    finally:
        event.remove(db.session, "after_commit", on_commit)


@pytest.mark.parametrize("path", ["/student/login", "/sysadmin/login"])
def test_INV_ARC_007__login_page_get_does_not_commit(client, app, path):
    with _commits() as commits:
        response = client.get(path)

    assert response.status_code == 200
    assert commits[0] == 0


def test_INV_ARC_007__teacher_class_selector_get_does_not_commit(client, app):
    initialize_as_teacher("chemistry_p1", client, app)

    with _commits() as commits:
        response = client.get("/admin/select-class-context")

    assert response.status_code == 200
    assert commits[0] == 0


def test_INV_ARC_007__teacher_class_selection_post_still_commits_the_switch(client, app):
    """Moving the FEAT off GET must not lose the write on POST."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)

    with _commits() as commits:
        response = client.post(
            "/admin/select-class-context", data={"class_id": classroom.class_id}
        )

    assert response.status_code == 302
    assert commits[0] >= 1
    db.session.expire_all()
    user = db.session.get(User, classroom.teacher_user.id)
    assert user.last_active_class_id == classroom.class_id
    assert user.last_active_seat_id == classroom.teacher_seat.id
