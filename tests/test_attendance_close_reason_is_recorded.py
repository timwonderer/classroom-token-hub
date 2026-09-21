"""An attendance close says WHY it happened (finding 38).

Three codes described four events: a student choosing to stop, the daily cap
closing the session, and the class day ending all wrote ``done_for_day``. The
two system cases were indistinguishable from each other and read, in the
timeline, as though the student had decided to stop.

That matters because attendance rows are permanent and are never corrected
(DOM-PROD-001 §108). The row IS the evidence a teacher weighs when deciding
whether to reverse the payroll it produced — the only remedy the domain offers
(§187). "Why did I stop at 22:10?" has to be answerable from the record. The
scheduled job already composed the answer and passed it to a ``reason``
parameter with no column behind it.

Verified live on 2026-09-21: seat 6 clocked in at 03:40:06Z, and the job wrote
an ``inactive`` row at exactly 05:10:06Z — clock-in plus 5400s to the
microsecond, with mechanism ``system`` — carrying ``done_for_day``.
"""

from __future__ import annotations

import pytest

from app.models import AttendanceReasonCode, TERMINAL_DAY_REASON_CODES


def test_the_vocabulary_distinguishes_the_three_terminal_events():
    codes = {c.value for c in AttendanceReasonCode}
    assert {"done_for_day", "daily_limit_reached", "end_of_day"} <= codes


def test_every_terminal_code_locks_the_day():
    """The lockout set must contain all three, or a capped student works past the cap.

    This is the regression the change risks. `prod.py` refuses a new clock-in
    when a terminal row exists for the class day; when that query matched only
    `done_for_day`, introducing a distinct `daily_limit_reached` code would have
    silently reopened the day for exactly the student the cap had just stopped.
    """
    assert TERMINAL_DAY_REASON_CODES == {
        AttendanceReasonCode.DONE_FOR_DAY.value,
        AttendanceReasonCode.DAILY_LIMIT_REACHED.value,
        AttendanceReasonCode.END_OF_DAY.value,
    }
    assert AttendanceReasonCode.START_WORK.value not in TERMINAL_DAY_REASON_CODES
    assert AttendanceReasonCode.HALL_PASS.value not in TERMINAL_DAY_REASON_CODES, (
        "a hall pass interrupts a session; it does not end the working day"
    )


@pytest.mark.parametrize(
    "module_path,description",
    [
        ("app/feats/prod.py", "the clock-in lockout"),
        ("app/attendance.py", "the done-today query"),
    ],
)
def test_both_lockout_readers_consider_the_whole_set(module_path, description):
    """Neither reader may match a single code."""
    from pathlib import Path

    source = Path(module_path).read_text(encoding="utf-8")
    assert "TERMINAL_DAY_REASON_CODES" in source, (
        f"{description} does not use the terminal-code set"
    )
    assert "reason_code == AttendanceReasonCode.DONE_FOR_DAY.value" not in source, (
        f"{description} still matches only done_for_day, so a student closed by "
        f"the daily cap or the end of day could start work again"
    )


def test_the_scheduled_job_records_which_close_it_performed():
    from pathlib import Path

    source = Path("app/scheduled_tasks.py").read_text(encoding="utf-8")
    assert "AttendanceReasonCode.DAILY_LIMIT_REACHED" in source
    assert "AttendanceReasonCode.END_OF_DAY" in source
    assert "reason_code=AttendanceReasonCode.DONE_FOR_DAY," not in source, (
        "the job still hardcodes done_for_day for both of its branches"
    )


def test_a_day_ending_on_an_open_session_is_not_recorded_as_a_student_choice():
    """DOM-PROD-001 §312's auto-close is the day ending, not the student stopping."""
    from pathlib import Path

    source = Path("app/feats/prod.py").read_text(encoding="utf-8")
    marker = source.index("closing_row = AttendanceSession(")
    block = source[marker: marker + 600]
    assert "AttendanceReasonCode.END_OF_DAY.value" in block, block[:300]
