"""The banking student filter never puts a student name in a URL.

A GET query string reaches the nginx access log, browser history and Referer, so the
filter names the student by seat public_id (INV-ARC-005 §V; DOM-OPS-001 §7).
"""

from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from app.extensions import db
from app.feats.base import FEATContext
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher
from tests.helpers.ledger import create_ledger_idempotent_transaction


def _seed(classroom, student, count):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"banking-filter:{student.seat_id}"):
        for i in range(count):
            create_ledger_idempotent_transaction(
                idempotency_key=f"banking-filter:{student.seat_id}:{i}",
                seat_id=student.seat_id,
                class_id=classroom.class_id,
                amount=Decimal("1.00"),
                account_type="checking",
                type="manual_payment",
                description="Banking filter seed",
            )
    db.session.commit()


def _page_urls(html):
    soup = BeautifulSoup(html, "html.parser")
    return [a["href"] for a in soup.find_all("a", href=True)] + [
        f.get("action", "") for f in soup.find_all("form")
    ]


def test_banking_student_filter_urls_carry_public_id_not_name(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    alice, bob = classroom.students[0], classroom.students[1]
    _seed(classroom, alice, 60)
    _seed(classroom, bob, 3)

    page = client.get("/admin/banking")
    soup = BeautifulSoup(page.get_data(as_text=True), "html.parser")
    picker = soup.find("select", attrs={"name": "student"})
    assert picker is not None
    assert alice.seat.public_id in {o.get("value") for o in picker.find_all("option")}
    assert soup.find("input", attrs={"name": "student"}) is None

    response = client.get(f"/admin/banking?student={alice.seat.public_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    pagination = [u for u in _page_urls(html) if "page=" in u]
    assert pagination, "60 rows must paginate so the carried filter is exercised"
    names = {alice.first_name, alice.last_name, bob.first_name, bob.last_name}
    for url in _page_urls(html):
        assert not any(name.lower() in url.lower() for name in names), url
    for url in pagination:
        assert parse_qs(urlparse(url).query)["student"] == [alice.seat.public_id]
    assert "Showing 50 of 60 transactions" in " ".join(html.split())


def test_banking_student_filter_ignores_names_and_other_classes(client, app):
    other = initialize("ap_csp_p3", app)
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    alice = classroom.students[0]
    _seed(classroom, alice, 2)
    _seed(other, other.students[0], 2)

    by_name = client.get(f"/admin/banking?student={alice.first_name}").get_data(as_text=True)
    assert "Showing 0 of 0 transactions" in " ".join(by_name.split())

    foreign = client.get(
        f"/admin/banking?student={other.students[0].seat.public_id}"
    ).get_data(as_text=True)
    assert "Showing 0 of 0 transactions" in " ".join(foreign.split())
