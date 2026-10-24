"""SPEC-TIME-001 §XII–§XIII: application code obtains every temporal value from the resolver."""

from pathlib import Path

import pytest

from tests.guards.temporal_resolver_conformance import find_violations, scan_repository

REPO = Path(__file__).resolve().parent.parent


def test_SPEC_TIME_001__no_time_logic_outside_the_resolver():
    hits, parsed = scan_repository(REPO)
    # The predecessor guard scanned a directory that did not exist for three months.
    assert parsed >= 150, f"scanned only {parsed} files: the guard is not looking at app/"
    assert not hits, "Use canonical_temporal_resolver primitives (SPEC-TIME-001):\n" + "\n".join(
        f"{h.path}:{h.line}: {h.rule}" for h in hits
    )


@pytest.mark.parametrize("source", [
    "from datetime import datetime, timezone\nx = datetime.now(timezone.utc)\n",
    "import datetime as dt\nx = dt.datetime.utcnow()\n",
    "from datetime import date\nx = date.today()\n",
    "import time\nx = time.time()\n",
    "from app.utils.canonical_temporal_resolver import utc_now\n",
    "from app.utils.canonical_temporal_resolver import canonical_temporal_resolver, ensure_utc\n",
    "x = utc_now()\n",
    "x = ensure_utc(row.created_at)\n",
    "from sqlalchemy import func\nx = func.now()\n",
    "local = ts.astimezone(tz)\n",
    "from datetime import timezone\naware = ts.replace(tzinfo=timezone.utc)\n",
    "import pytz\ntz = pytz.timezone(name)\n",
    "from zoneinfo import ZoneInfo\ntz = ZoneInfo(name)\n",
    "local = tz.localize(naive)\n",
    "from datetime import timedelta\ndeadline = start + timedelta(days=5)\n",
    "from dateutil.relativedelta import relativedelta\nnext_due = due + relativedelta(months=1)\n",
    "seconds = (end - start).total_seconds()\n",
    "from datetime import datetime, time\nmidnight = datetime.combine(day, time.min)\n",
    "day = row.created_at.date()\n",
])
def test_mutation_proof_reports_each_prohibited_pattern(source):
    assert find_violations(source), source


@pytest.mark.parametrize("source", [
    "from app.utils.canonical_temporal_resolver import SYSTEM_LEVEL_EVALUATION, canonical_temporal_resolver\n"
    "now = canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive='current_time').canonical_now_utc\n",
    "# datetime.now() is prohibited\nx = 'utc_now() in prose'\n",
    "from datetime import date\nd = date.fromisoformat(form_value)\n",
    "import time\nstarted = time.perf_counter()\n",
    "value = request.form.get('date')\n",
    "import pytz\nvalid = name in pytz.all_timezones_set\n",
])
def test_resolver_calls_and_non_temporal_code_are_not_reported(source):
    assert not find_violations(source), source
