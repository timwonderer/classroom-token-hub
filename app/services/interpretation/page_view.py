"""Interpretation page view model (INV-ARC-022 page-level composition).

Aggregates the ITR domain-owned presentation objects into a single page contract
for the teacher Interpretation page. The route assembles this from lawful domain
reads and hands it to the template; it reconstructs no domain truth and is not
itself a presentation model (INV-ARC-022).

Empty history is a first-class state: a class with no ``interpretation_cycle_record``
yet — e.g. a newly created class before its first payroll completion — is
``awaiting_first_completed_cycle``, not an error and not a cue to compute anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from app.services.interpretation.presentation import (
    InterpretationCycleSummary,
    InterpretationCycleView,
)
from app.services.interpretation.read_service import (
    get_cycle_view,
    get_latest_cycle_view,
    list_cycle_summaries,
)
from app.utils.temporal_display import format_date

STATE_HAS_HISTORY = "has_history"
STATE_AWAITING_FIRST_CYCLE = "awaiting_first_completed_cycle"


@dataclass(frozen=True)
class CycleOption:
    """One entry in the completed-cycle selector, its date as class-local text."""

    payroll_cycle_id: str
    cycle_completed_display: str


@dataclass(frozen=True)
class InterpretationPageView:
    """Single page contract for the Interpretation page."""

    state: str  # STATE_HAS_HISTORY | STATE_AWAITING_FIRST_CYCLE
    latest_cycle: InterpretationCycleView | None
    history: tuple[InterpretationCycleSummary, ...]
    selected_cycle_id: str | None
    history_options: tuple[CycleOption, ...] = ()
    latest_cycle_completed_display: str | None = None


def build_interpretation_page_view(
    class_id: str, *, selected_cycle_id: str | None = None
) -> InterpretationPageView:
    """Assemble the Interpretation page from class-scoped ITR reads.

    When ``selected_cycle_id`` is given it is resolved **under this class** (class
    isolation, INV-CORE-000): a cycle that does not belong to ``class_id`` resolves
    to ``latest_cycle=None`` so the route can fail closed. With no selection, the
    most recently completed cycle is shown. All reads consume frozen records; no
    Interpretation is recomputed (INV-ARC-007).
    """
    history = tuple(list_cycle_summaries(class_id))
    if selected_cycle_id:
        latest_cycle = get_cycle_view(class_id, selected_cycle_id)
        resolved_selection = selected_cycle_id
    else:
        latest_cycle = get_latest_cycle_view(class_id)
        resolved_selection = latest_cycle.cycle.payroll_cycle_id if latest_cycle else None

    state = STATE_HAS_HISTORY if history else STATE_AWAITING_FIRST_CYCLE
    # Dates render in the class's own timezone (CLE), as the page always has.
    temporal_context = SimpleNamespace(class_id=class_id)
    return InterpretationPageView(
        state=state,
        latest_cycle=latest_cycle,
        history=history,
        selected_cycle_id=resolved_selection,
        history_options=tuple(
            CycleOption(s.payroll_cycle_id, format_date(temporal_context, s.cycle_completed_at))
            for s in history
        ),
        latest_cycle_completed_display=(
            format_date(temporal_context, latest_cycle.cycle.cycle_completed_at) if latest_cycle else None
        ),
    )
