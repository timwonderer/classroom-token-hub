"""Support ticket categories exist without anyone visiting a page first.

On 2026-09-27 every teacher support ticket in production returned 500. The
``issue_categories`` table was empty: the only thing that ever filled it was a
write inside two GET handlers (an INV-ARC-007 violation), and the admin route
then mapped each topic to a category name that no seed had ever created, fell
back to ``IssueCategory.query.first()``, and dereferenced ``None``.

The existing ticket tests all seeded the categories themselves before posting,
so none of them could see it. These tests deliberately do not.
"""

from __future__ import annotations

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import Issue, IssueCategory
from app.utils.issue_categories import (
    DEFAULT_GENERAL_CATEGORIES,
    DEFAULT_TRANSACTION_CATEGORIES,
)
from tests.helpers.support_domain import (
    initialize_support_student,
    initialize_support_teacher,
    submit_support_ticket,
)


def _category_rows():
    return {
        c.name: (c.description, c.category_type, c.display_order, c.is_active)
        for c in IssueCategory.query.all()
    }


def _remove_all_categories(key: str) -> None:
    """Put the database in the state production was in: no categories at all."""
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"ticket-categories:{key}"):
        IssueCategory.query.delete()
        db.session.flush()


def test_DOM_SUP_001__migrations_alone_seed_every_default_category(app):
    """A freshly migrated database has the full default set, exactly as
    ``app/utils/issue_categories.py`` defines it."""
    with app.app_context():
        expected = {
            c["name"]: (c["description"], c["category_type"], c["display_order"], True)
            for c in DEFAULT_TRANSACTION_CATEGORIES + DEFAULT_GENERAL_CATEGORIES
        }
        assert _category_rows() == expected


@pytest.mark.parametrize(
    ("topic", "category_name"),
    [
        ("general", "General question"),
        ("bug", "Bug report"),
        ("feature", "Feature request"),
    ],
)
def test_DOM_SUP_001__teacher_ticket_files_under_its_topic_category(client, topic, category_name):
    """No test-side seeding: the categories the migration created are enough."""
    initialize_support_teacher("chemistry_p1", client, client.application)

    response = submit_support_ticket(
        client, issue_category=topic, title=f"Topic {topic}", description="Filed by topic."
    )

    assert response.status_code == 200
    assert b"submitted directly to system administration" in response.data
    issue = Issue.query.filter_by(title=f"Topic {topic}").one()
    assert issue.category.name == category_name


def test_DOM_SUP_001__missing_category_refuses_the_ticket_instead_of_500(client):
    initialize_support_teacher("chemistry_p1", client, client.application)
    _remove_all_categories("missing")

    response = submit_support_ticket(
        client, issue_category="bug", title="No category", description="Nothing to file under."
    )

    assert response.status_code == 200
    assert b"Your ticket was not sent" in response.data
    assert Issue.query.filter_by(title="No category").count() == 0


def test_DOM_SUP_001__missing_category_is_never_replaced_by_another(client):
    """With its own category gone, a bug report must not be filed under
    whatever category happens to sort first."""
    initialize_support_teacher("chemistry_p1", client, client.application)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="ticket-categories:inactive"):
        IssueCategory.query.filter_by(name="Bug report").update({"is_active": False})
        db.session.flush()

    submit_support_ticket(
        client, issue_category="bug", title="Inactive category", description="Should not file."
    )

    assert Issue.query.filter_by(title="Inactive category").count() == 0


def test_INV_ARC_007__student_help_page_get_writes_no_categories(client):
    initialize_support_student("chemistry_p1", client, client.application)
    _remove_all_categories("student-get")

    response = client.get("/student/help-support")

    assert response.status_code == 200
    db.session.expire_all()
    assert IssueCategory.query.count() == 0


def test_INV_ARC_007__admin_issues_queue_get_writes_no_categories(client):
    initialize_support_teacher("chemistry_p1", client, client.application)
    _remove_all_categories("admin-get")

    response = client.get("/admin/issues")

    assert response.status_code == 200
    db.session.expire_all()
    assert IssueCategory.query.count() == 0
