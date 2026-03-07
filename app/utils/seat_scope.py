"""Helpers for transitional student->seat scoped queries."""

import sqlalchemy as sa


def get_seat_ids_for_student_join(student_id: int, join_code: str) -> list[int]:
    """Return seat IDs bound to a student and join code."""
    from app.models import Seat

    return [
        row[0]
        for row in Seat.query.with_entities(Seat.id).filter(
            Seat.student_id == student_id,
            Seat.join_code == join_code,
        ).all()
    ]


def transaction_scope_filter(TransactionModel, student_id: int, seat_ids: list[int]):
    """Return dual-read filter: prefer seat_id, fallback to legacy student_id rows."""
    if seat_ids:
        return sa.or_(
            sa.and_(TransactionModel.seat_id.in_(seat_ids), TransactionModel.seat_id.is_not(None)),
            sa.and_(TransactionModel.seat_id.is_(None), TransactionModel.student_id == student_id),
        )
    return TransactionModel.student_id == student_id


def seat_scoped_filter(Model, student_id: int, seat_ids: list[int], seat_field: str = "seat_id", student_field: str = "student_id"):
    """Return dual-read filter for models that carry both seat_id and student_id."""
    seat_col = getattr(Model, seat_field)
    student_col = getattr(Model, student_field)
    if seat_ids:
        return sa.or_(
            sa.and_(seat_col.in_(seat_ids), seat_col.is_not(None)),
            sa.and_(seat_col.is_(None), student_col == student_id),
        )
    return student_col == student_id
