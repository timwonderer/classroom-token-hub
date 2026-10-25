"""Audit O3: the hourly scheduled jobs must not all become due in one minute.

``SCHEDULED_JOB_SPECS`` used to declare nine jobs as ``interval, hours=1``.
APScheduler's interval trigger anchors its first fire to the instant the job
was added — the same instant, for every job, since ``init_scheduled_tasks``
adds them all in one loop at process start. So all nine became due in the
same minute, every hour, for the life of the process: nine jobs competing for
APScheduler's thread pool and the database inside the one gunicorn worker that
also serves requests, worst right at the top of a school's class periods.

The fix is a ``cron`` trigger on a distinct minute per job: the cadence stays
hourly (no ``hour`` key means every hour), but each job's minute is fixed and
spread across the hour, and that minute survives process restarts instead of
drifting with each deploy.

This is a mutation-proof guard, not a smoke test: it fails for the exact shape
of the original defect (all nine on the same minute) and proves itself by
asserting on today's schedule, not by re-describing it.
"""

from __future__ import annotations

from app.scheduled_tasks import SCHEDULED_JOB_SPECS

_FORMERLY_INTERVAL_HOURLY_IDS = frozenset({
    "expired_teacher_signups",
    "stale_teacher_accounts",
    "enforce_daily_limits",
    "rent_reconciliation",
    "automatic_payroll",
    "insurance_renewal",
    "collective_goal_expiry",
    "ledger_settlement",
    "savings_interest_payout",
})

# Jobs pinned to one fixed hour:minute per day (never touched by O2/O3) that
# an every-hour job can still collide with once a day, at that hour. A job
# scheduled every hour at the same minute as one of these fires alongside it
# on that one hour too, competing for the same thread pool and DB connection.
_FIXED_HOUR_DAILY_IDS = frozenset({
    "database_maintenance",
    "audit_invariant_check",
    "insurance_expiry",
})


def _hourly_specs():
    specs = [spec for spec in SCHEDULED_JOB_SPECS if spec.id in _FORMERLY_INTERVAL_HOURLY_IDS]
    assert len(specs) == len(_FORMERLY_INTERVAL_HOURLY_IDS), (
        "expected every formerly-interval hourly job still to be registered"
    )
    return specs


def test_no_two_hourly_jobs_share_a_minute():
    """Mutation proof: reverting any one job to ``interval, hours=1`` collides.

    An ``interval`` trigger carries no ``minute`` key at all, so it would fail
    the cron-with-minute assertion below before it could even collide — this
    also catches a partial revert, not only two jobs sharing a minute.
    """
    specs = _hourly_specs()
    for spec in specs:
        assert spec.trigger == "cron", (
            f"{spec.id} is not cron-scheduled; an interval trigger anchors to "
            "process start and reintroduces the O3 thundering herd"
        )
        assert "hour" not in spec.trigger_kwargs, (
            f"{spec.id} is pinned to a specific hour; it must run every hour"
        )
        minute = spec.trigger_kwargs.get("minute")
        assert isinstance(minute, int) and 0 <= minute < 60, (
            f"{spec.id} has no valid cron minute: {spec.trigger_kwargs!r}"
        )

    minutes = [spec.trigger_kwargs["minute"] for spec in specs]
    assert len(minutes) == len(set(minutes)), (
        f"two or more hourly jobs share a minute, reintroducing the O3 "
        f"thundering herd: {sorted(minutes)}"
    )


def test_hourly_jobs_do_not_share_a_minute_with_a_fixed_hour_job():
    """An every-hour job must not land on the same minute as a once-daily job.

    ``database_maintenance`` (02:00), ``audit_invariant_check`` (03:00) and
    ``insurance_expiry`` (04:00) each fire once a day at a fixed hour. If an
    every-hour job shares that minute, it collides with each of them once a
    day too -- the same thundering-herd failure mode O3 fixed, just rarer.
    """
    by_id = {spec.id: spec for spec in SCHEDULED_JOB_SPECS}
    fixed_minutes = {
        by_id[job_id].id: by_id[job_id].trigger_kwargs["minute"]
        for job_id in _FIXED_HOUR_DAILY_IDS
    }

    for spec in _hourly_specs():
        minute = spec.trigger_kwargs["minute"]
        for fixed_id, fixed_minute in fixed_minutes.items():
            assert minute != fixed_minute, (
                f"{spec.id} shares minute {minute} with {fixed_id}, which "
                "fires once a day at that minute"
            )


def test_settlement_minute_still_precedes_interest_minute():
    """Interest accrues on posted balances, so settlement's minute comes first.

    Declaration order alone does not enforce this at runtime (the interest job
    discharges the dependency itself), but the minutes should still agree with
    the documented intent.
    """
    by_id = {spec.id: spec for spec in SCHEDULED_JOB_SPECS}
    settlement_minute = by_id["ledger_settlement"].trigger_kwargs["minute"]
    interest_minute = by_id["savings_interest_payout"].trigger_kwargs["minute"]
    assert settlement_minute < interest_minute
