"""The manual roster-dedupe CSVs are executable: import them, then claim.

tests/assets/roster_dedupe/ holds the rosters teachers paste for manual QA. This
test drives the same files through the upload route and the claim FEAT so the
documented expectations cannot drift from FEAT-IDEN-006 / FEAT-IDEN-001.
"""
import csv
from pathlib import Path

from app.extensions import db
from app.feats.identity_feat import activate_student_credentials, resolve_seat_claim
from app.hash_utils import hash_claim_name
from app.models import Seat
from tests.helpers.classroom_initializer import initialize_as_teacher

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "roster_dedupe"


def _load(name):
    with (ASSETS / name).open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert rows, f"{name} is empty"
    assert {row["Expect Claim Code"] for row in rows} <= {"yes", "no"}
    return rows


def _upload(client, rows):
    # Mirrors the grid: first three columns only; the expectation column never ships.
    response = client.post("/admin/upload-students", json={"students": [
        {"first_name": row["First Name"], "last_name": row["Last Name"], "notes": row["Notes"]}
        for row in rows
    ]})
    assert response.status_code == 200, response.json
    assert response.json["created"] == len(rows)


def _group(class_id, first, last):
    return Seat.query.filter_by(
        class_id=class_id, role="student", user_id=None,
        claim_first_name_hash=hash_claim_name(first, class_id=class_id, field="first"),
        claim_last_name_hash=hash_claim_name(last, class_id=class_id, field="last"),
    ).order_by(Seat.id).all()


def _assert_rows_claimable(classroom, rows):
    db.session.expire_all()
    for row in rows:
        first, last = row["First Name"], row["Last Name"]
        seats = _group(classroom.class_id, first, last)
        codes = [seat.dedupe_code for seat in seats]
        label = f"{first} {last} ({row['Notes']})"
        if row["Expect Claim Code"] == "no":
            assert len(seats) == 1 and codes == [None], label
            claim = resolve_seat_claim(join_code=classroom.join_code, first_name=first, last_name=last)
            assert claim.success and claim.seat_id == seats[0].id, label
            continue
        assert len(seats) > 1 and None not in codes and len(set(codes)) == len(codes), label
        ambiguous = resolve_seat_claim(join_code=classroom.join_code, first_name=first, last_name=last)
        assert ambiguous.error_code == "AMBIGUOUS_IDENTITY", label
        wrong = resolve_seat_claim(join_code=classroom.join_code, first_name=first,
                                   last_name=last, dedupe_code="ZZZZZZZZ")
        assert wrong.error_code == "INVALID_DEDUPE_CODE", label
        for seat in seats:
            claim = resolve_seat_claim(join_code=classroom.join_code, first_name=first,
                                       last_name=last, dedupe_code=seat.dedupe_code)
            assert claim.success and claim.seat_id == seat.id, label


def _claim(classroom, first, last, username):
    claim = resolve_seat_claim(join_code=classroom.join_code, first_name=first, last_name=last)
    assert claim.success, claim.error_code
    result = activate_student_credentials(
        seat_id=claim.seat_id, user_id=None, claim_generation=claim.claim_generation,
        username=username, pin="4826", passphrase="roster-dedupe-pass7",
        correlation_id="corr_roster_dedupe_claim", idempotency_key=f"roster-dedupe:claim:{username}",
    )
    assert result.success, result.error_code


def test_roster_dedupe_artifacts_import_and_claim(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    batch1, batch2 = _load("roster_dedupe_batch1.csv"), _load("roster_dedupe_batch2.csv")

    _upload(client, batch1)
    _assert_rows_claimable(classroom, batch1)

    # Batch 2 preconditions from its notes: batch-1 Ava is claimed first, and
    # existing namesake codes must survive the second import.
    _claim(classroom, "Ava", "Martinez", "roster-dedupe-ava")
    db.session.expire_all()
    sofia_codes = {seat.dedupe_code for seat in _group(classroom.class_id, "Sofia", "Nguyen")}

    _upload(client, batch2)
    _assert_rows_claimable(classroom, batch2)
    assert sofia_codes < {seat.dedupe_code for seat in _group(classroom.class_id, "Sofia", "Nguyen")}
