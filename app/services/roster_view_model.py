"""Read model for the teacher's Student Management roster.

The roster page used to receive thirteen separate template variables, three of
them parallel ``by_seat_id`` lookup dictionaries, and did its own joining and
formatting in markup: ``strftime`` on a raw timestamp, a ``balance < 0``
comparison choosing a CSS class, and a domain ``acquisition_type`` deciding a
badge colour. Presentation that depends on domain vocabulary belongs here, so
the template renders what it is handed (INV-ARC-022, MAP-UI-002).

One builder produces one frozen view: the claimed roster, the unclaimed seats,
and the class-level facts the page displays. Nothing here writes
(INV-ARC-007), and every read is scoped to one ``class_id``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models import IdentityProfile, Seat
from app.services.class_configuration_query_service import verify_teacher_owns_class
from app.services.entitlement_service import get_hall_pass_balance
from app.services.ledger_balance_query_service import get_batch_balances_by_class_seat


def _money(amount: Decimal) -> str:
    return f"${amount:.2f}"


@dataclass(frozen=True)
class RosterPrivilegeBadge:
    """One privilege a student holds, with its presentation already decided."""

    name: str
    description: str | None
    label: str
    variant: str
    title: str


@dataclass(frozen=True)
class RosterStudentRow:
    """A claimed student as the roster displays them."""

    seat_id: int
    public_id: str
    class_id: str
    full_name: str
    first_name: str
    last_name: str
    notes: str
    has_notes: bool
    username_display: str
    # Unclaim is generation-checked: a stale roster tab must not be able to
    # detach a seat that has since been re-claimed (DOM-IDEN-005 §Explicit Unclaim).
    claim_generation: int
    display_checking: str
    display_savings: str
    display_earnings: str
    checking_is_negative: bool
    hall_pass_balance: int
    privileges: tuple[RosterPrivilegeBadge, ...]

    @property
    def has_privileges(self) -> bool:
        return bool(self.privileges)


@dataclass(frozen=True)
class UnclaimedSeatRow:
    """An unclaimed roster seat: a provisioned placeholder awaiting a principal."""

    seat_id: int
    public_id: str
    class_id: str
    full_name: str
    claim_code: str | None
    claim_code_display: str
    display_added_on: str
    status_label: str


@dataclass(frozen=True)
class ClassRosterView:
    """Everything the Student Management roster renders for one class."""

    class_id: str
    class_label: str
    join_code: str | None
    section: str | None
    display_name: str | None
    students: tuple[RosterStudentRow, ...]
    unclaimed_seats: tuple[UnclaimedSeatRow, ...]
    recovery_min_students: int

    @property
    def claimed_count(self) -> int:
        return len(self.students)

    @property
    def unclaimed_count(self) -> int:
        return len(self.unclaimed_seats)

    @property
    def has_unclaimed_seats(self) -> bool:
        return bool(self.unclaimed_seats)

    @property
    def has_any_seats(self) -> bool:
        """True when the class holds at least one student seat, claimed or not."""
        return bool(self.students or self.unclaimed_seats)

    @property
    def all_seats_claimed(self) -> bool:
        """True only when seats exist and every one of them is claimed.

        The emptiness check alone is vacuously true: "every unclaimed seat is
        claimed" holds when there are no seats at all, so a brand-new class with
        nobody on the roster reported "all seats claimed" — the one state it
        certainly was not in. An empty roster is a third state, not a degenerate
        case of the second.
        """
        return self.has_any_seats and not self.unclaimed_seats

    @property
    def unclaimed_panel_label(self) -> str:
        """Heading for the join-code / unclaimed-seats panel.

        Decided here rather than in the template: three states, and the template
        renders what it is handed (INV-ARC-022, MAP-UI-002).
        """
        if self.has_unclaimed_seats:
            return f"Unclaimed seats ({self.unclaimed_count})"
        if self.all_seats_claimed:
            return "Join code — all seats claimed"
        return "Join code — no students added yet"

    @property
    def recovery_at_risk(self) -> bool:
        """True while this class holds too few claimed students for recovery.

        Student-assisted teacher recovery draws its witnesses from claimed
        students in each class (DOM-IDEN-003 §IX), so a class below the minimum
        blocks recovery for the whole account.
        """
        return self.claimed_count < self.recovery_min_students


def _class_label(class_row) -> str:
    parts = [part for part in (class_row.section, class_row.display_name) if part]
    return " - ".join(parts) or class_row.class_id


def _privilege_badges(privileges) -> tuple[RosterPrivilegeBadge, ...]:
    """Decide each privilege's badge here, not in the template.

    ``source`` is domain vocabulary — ``rent`` for a rent-cycle perk, anything
    else for an individual purchase — and the template should not be reading it
    to pick a colour.
    """
    badges = []
    for privilege in privileges or []:
        from_rent = privilege.get("source") == "rent"
        badges.append(
            RosterPrivilegeBadge(
                name=privilege.get("name") or "Privilege",
                description=privilege.get("description"),
                label=privilege.get("name") or "Privilege",
                variant="success" if from_rent else "info",
                title="Covered by rent" if from_rent else "Individually purchased",
            )
        )
    return tuple(badges)


def build_class_roster_view(
    *,
    class_id: str,
    teacher_user_id: int,
    recovery_min_students: int,
    privilege_resolver=None,
) -> ClassRosterView | None:
    """Build the roster view for one teacher-owned class, or None if not owned.

    ``privilege_resolver`` is injected so the Store-domain read stays a
    dependency rather than an import cycle; it is called per seat and may be
    omitted, in which case no privilege badges are produced.
    """
    if not class_id:
        return None
    class_row = verify_teacher_owns_class(class_id, teacher_user_id)
    if not class_row:
        return None

    seats = (
        Seat.query
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .filter(Seat.class_id == class_id)
        .all()
    )

    claimed = sorted(
        (
            seat for seat in seats
            if seat.role == "student" and seat.user_id is not None and seat.claimed_at is not None
        ),
        key=lambda seat: (
            (seat.identity_profile.first_name if seat.identity_profile else "").lower(),
            (seat.identity_profile.last_name if seat.identity_profile else "").lower(),
            seat.id,
        ),
    )
    unclaimed = sorted(
        (seat for seat in seats if seat.user_id is None and seat.claimed_at is None),
        key=lambda seat: (
            (seat.identity_profile.first_name if seat.identity_profile else "").lower(),
            seat.id,
        ),
    )

    balances = get_batch_balances_by_class_seat([(class_id, seat.id) for seat in claimed])

    student_rows = []
    for seat in claimed:
        profile = seat.identity_profile
        scoped = balances.get((str(class_id), seat.id)) or {
            "checking_cents": 0, "savings_cents": 0, "earnings": Decimal("0.00"),
        }
        checking = Decimal(scoped["checking_cents"]) / 100
        savings = Decimal(scoped["savings_cents"]) / 100
        earnings = Decimal(scoped.get("earnings") or 0)
        notes = (profile.notes if profile and profile.notes else "") or ""
        privileges = (
            privilege_resolver(seat, class_id, seat.id) if privilege_resolver else []
        )
        student_rows.append(
            RosterStudentRow(
                seat_id=seat.id,
                public_id=seat.public_id,
                class_id=seat.class_id,
                full_name=profile.full_name if profile else "",
                first_name=profile.first_name if profile else "",
                last_name=profile.last_name if profile else "",
                notes=notes,
                has_notes=bool(notes.strip()),
                # The roster shows whether a login exists, never the username
                # itself: it is stored only as an unsalted lookup digest.
                username_display="Set" if seat.user_id else "Not Set",
                claim_generation=seat.claim_generation,
                display_checking=_money(checking),
                display_savings=_money(savings),
                display_earnings=_money(earnings),
                checking_is_negative=checking < 0,
                hall_pass_balance=get_hall_pass_balance(seat.id, class_id),
                privileges=_privilege_badges(privileges),
            )
        )

    unclaimed_rows = tuple(
        UnclaimedSeatRow(
            seat_id=seat.id,
            public_id=seat.public_id,
            class_id=seat.class_id,
            full_name=seat.identity_profile.full_name if seat.identity_profile else "Unknown",
            claim_code=seat.dedupe_code,
            # A seat only needs a distinguishing code when it shares a name.
            claim_code_display=seat.dedupe_code or "Not needed",
            display_added_on=seat.created_at.strftime("%Y-%m-%d") if seat.created_at else "N/A",
            status_label="Waiting for Claim",
        )
        for seat in unclaimed
    )

    return ClassRosterView(
        class_id=class_id,
        class_label=_class_label(class_row),
        join_code=class_row.join_code,
        section=class_row.section,
        display_name=class_row.display_name,
        students=tuple(student_rows),
        unclaimed_seats=unclaimed_rows,
        recovery_min_students=recovery_min_students,
    )
